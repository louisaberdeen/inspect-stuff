# Proxmox on this laptop (nested) — setup for proxmox-pi/

The sandbox plugin (`inspect_proxmox_sandbox`, UK AISI) ships a script that builds
a correctly configured nested Proxmox 9 for you: SDN + dnsmasq, storage content
types, a firewall that blocks the 169.254.0.0/16 metadata range, and the patched
qemu it needs for static IPs. Use it; don't hand-install.

## Budget first
- **Disk:** free ~40 GB. The Proxmox disk is thin (sparse), but ISO, the docker
  build, the Proxmox install, a patched-qemu build on first boot, the Ubuntu image
  and the template all add up. With 13 GB free it will fail partway through.
- **RAM:** the script gives Proxmox 75% of RAM, **minimum 4096 MB** (`capacity.sh`).
  On a 5 GB laptop, close everything else. Sandbox VMs are 1 GB (Ubuntu) or 512 MB (Alpine) and
  `run.sh` runs one sample at a time.
- KVM nested virtualisation is already on (`/sys/module/kvm_*/parameters/nested` = 1).
  Docker is installed and you're in the `docker` group.

## 1. Build the Proxmox VM (once, ~30–60 min)
No ISO download needed: the script fetches the Proxmox VE 9.0 ISO itself, builds an
unattended installer from it, and its first boot `apt upgrade`s to the latest 9.x.
```bash
pip show inspect-proxmox-sandbox >/dev/null   # installed in ../inspect_ai/.venv
mkdir -p ~/proxmox-build && cd ~/proxmox-build
cp ~/Documents/inspect/inspect_ai/.venv/lib/python3.13/site-packages/proxmoxsandbox/scripts/virtualized_proxmox/build_proxmox_auto.sh .
bash build_proxmox_auto.sh        # apt installs virt-manager/libvirt, builds the ISO, installs PVE
```
It adds you to the `libvirt` group, so log out and back in if later `virsh` calls
complain. The script's own `answers.toml` sets the root password to `Password2.0`.
Each clone from step 2 gets a random password.

## 2. Start an instance
```bash
cd ~/proxmox-build && ./vend.sh 1
```
It prints `PROXMOX_PORT=11001`, `PROXMOX_PASSWORD=...` and the rest. Copy them into
`proxmox-pi/.env` (start from `.env.example`). `PROXMOX_HOST=127.0.0.1`, because
vend forwards the API to localhost. Web UI: https://127.0.0.1:11001 (user `root`, realm PAM).

## 3. Build the pi template (once per Proxmox instance)
In the web UI, open node `proxmox` → **>_ Shell**, paste the contents of
`make_template.sh` into a file there, and run one or both:
```bash
bash make_template.sh           # Ubuntu 24.04 -> tag inspect-pi         (1 GB per sandbox VM)
bash make_template.sh alpine    # Alpine 3.24  -> tag inspect-pi-alpine  (512 MB, best for this laptop)
```
Each takes about 5 min. `qm list` should then show the templates (tags `inspect;inspect-pi...`).

## 4. Run
```bash
cd ~/Documents/inspect/proxmox-pi
source ../inspect_ai/.venv/bin/activate
./run.sh https://huggingface.co/datasets/<org>/<name> https://huggingface.co/Qwen/Qwen3-32B-AWQ --limit 3
./run.sh https://huggingface.co/datasets/ai-safety-institute/AgentHarm https://huggingface.co/Qwen/Qwen3-32B-AWQ --limit 3
```
Generic datasets default to columns `input`/`target` and split `test`. Override them with
`-T input_field=question -T target_field=answer -T split=validation` (and `-T name=<config>`).
Add `-T image=alpine` to use the Alpine template.

## Stop (RAM + money)
```bash
colab stop -s vllm                  # the A100 bills until stopped
virsh shutdown proxmox-clone-1      # frees the laptop's RAM
# delete it:  virsh destroy proxmox-clone-1; virsh undefine --nvram --remove-all-storage proxmox-clone-1
```
