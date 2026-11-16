#!/usr/bin/env bash
# Run ON the Proxmox host, once per distro (web UI -> node "proxmox" -> >_ Shell,
# then paste, or scp it over). Builds the VM template that task.py clones per sample.
#
#   bash make_template.sh            # Ubuntu 24.04  -> tag inspect-pi         (VM id 9000)
#   bash make_template.sh alpine     # Alpine 3.24   -> tag inspect-pi-alpine  (VM id 9001)
#
# This is the VM version of sandbox-pi's multi-stage Dockerfile: the build VM gets
# internet (on a temporary SNAT subnet) to install node + pi + the bridge extension.
# Its NIC is then deleted, and task.py attaches clones to an offline subnet.
set -euo pipefail
DISTRO=${1:-ubuntu}
STORAGE=${STORAGE:-local}
NODE=$(hostname)

case "$DISTRO" in
  ubuntu)
    ID=9000; TAG=inspect-pi
    URL=https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img
    PACKAGES="qemu-guest-agent, python3, curl, ca-certificates"
    INSTALL='
  - systemctl enable --now qemu-guest-agent
  - curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  - apt-get install -y nodejs
  - curl -fsSL https://pi.dev/install.sh | HOME=/root sh' ;;
  alpine)
    # "generic" = reads Proxmox's NoCloud cloud-init drive; bios = default SeaBIOS
    ID=9001; TAG=inspect-pi-alpine
    URL=https://dl-cdn.alpinelinux.org/alpine/v3.24/releases/cloud/generic_alpine-3.24.1-x86_64-bios-cloudinit-r0.qcow2
    # bash: pi's bash tool shells out to it (busybox ash isn't bash)
    PACKAGES="qemu-guest-agent, nodejs, npm, python3, bash, curl, ca-certificates"
    INSTALL='
  - rc-update add qemu-guest-agent default
  - rc-service qemu-guest-agent start
  - npm install -g @earendil-works/pi-coding-agent' ;;
  *) echo "usage: $0 [ubuntu|alpine]"; exit 1 ;;
esac
IMG=/var/lib/vz/template/iso/$(basename "$URL")
[ -f "$IMG" ] || wget -O "$IMG" "$URL"

# temporary build network with internet (same shape the plugin uses for its own templates)
if ! pvesh get /cluster/sdn/vnets/pibuild >/dev/null 2>&1; then
  pvesh create /cluster/sdn/zones --type simple --zone pibz --dhcp dnsmasq --ipam pve
  pvesh create /cluster/sdn/vnets --vnet pibuild --zone pibz
  pvesh create /cluster/sdn/vnets/pibuild/subnets --type subnet --subnet 192.168.96.0/24 \
    --gateway 192.168.96.1 --snat 1 --dhcp-range start-address=192.168.96.50,end-address=192.168.96.100
  pvesh set /cluster/sdn
fi

mkdir -p /var/lib/vz/snippets
cat > "/var/lib/vz/snippets/$TAG.yaml" <<YAML
#cloud-config
package_update: true
packages: [$PACKAGES]
write_files:
  # Same provider as sandbox-pi/Dockerfile.multistage: pi ignores OPENAI_BASE_URL,
  # so register "vllm" pointing at the Inspect bridge inside the VM.
  - path: /opt/pi-bridge/index.ts
    content: |
      import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
      export default function (pi: ExtensionAPI) {
        pi.registerProvider("vllm", {
          name: "Inspect Bridge",
          baseUrl: "http://127.0.0.1:13131/v1",
          apiKey: "inspect-bridge",
          api: "openai-completions",
          models: [{
            id: "inspect", name: "Inspect Bridge Model",
            reasoning: true, input: ["text"],
            cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
            contextWindow: 8192, maxTokens: 2048,
            compat: { maxTokensField: "max_tokens", supportsReasoningEffort: false }
          }]
        });
      }
runcmd:$INSTALL
  - HOME=/root pi install /opt/pi-bridge -a
  - mkdir -p /workspace
  - cloud-init clean --logs
  - poweroff
YAML

qm create "$ID" --name "$TAG" --memory 2048 --cores 2 --ostype l26 \
  --scsihw virtio-scsi-pci --agent enabled=1 --serial0 socket --vga serial0 \
  --net0 virtio,bridge=pibuild
qm set "$ID" --scsi0 "$STORAGE:0,import-from=$IMG"
qm resize "$ID" scsi0 +4G
qm set "$ID" --ide2 "$STORAGE:cloudinit" --boot order=scsi0 --ipconfig0 ip=dhcp \
  --cicustom "user=$STORAGE:snippets/$TAG.yaml"

qm start "$ID"
echo "installing node + pi in VM $ID (powers off when done, ~5 min)..."
while qm status "$ID" | grep -q running; do sleep 10; done

# no NIC in the template: clones get only the offline one task.py asks for
qm set "$ID" --delete net0,ide2,cicustom
qm template "$ID"
qm set "$ID" --tags "inspect;$TAG"   # plugin looks up templates tagged "inspect" + our tag
echo "template $ID ready (tag $TAG) on node $NODE"
