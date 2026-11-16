from agent import pi_agent
from proxmoxsandbox.schema import (
    DhcpRange,
    ProxmoxSandboxEnvironmentConfig,
    SdnConfig,
    SubnetConfig,
    VmConfig,
    VmNicConfig,
    VmSourceConfig,
    VnetConfig,
)

from inspect_ai import Task, task
from inspect_ai.dataset import FieldSpec, hf_dataset
from inspect_ai.scorer import includes
from inspect_ai.util import SandboxEnvironmentSpec

# The Proxmox equivalent of network_mode: none. The VM sits on its own SDN subnet
# with snat=False, so it has no route out. The plugin's sdn_config="auto" would turn
# SNAT on. The Inspect bridge still works because it relays over the guest agent,
# not the network.
# ponytail: fixed CIDR means one sample at a time (run.sh passes --max-samples 1).
# For parallel samples, give each Sample its own sandbox spec with a unique subnet.
OFFLINE = SdnConfig(
    vnet_configs=(
        VnetConfig(
            alias="offline",
            subnets=(
                SubnetConfig(
                    cidr="192.168.97.0/24",
                    gateway="192.168.97.1",
                    snat=False,
                    dhcp_ranges=(DhcpRange(start="192.168.97.50", end="192.168.97.100"),),
                ),
            ),
        ),
    ),
)

# image -> (template tag from make_template.sh, VM RAM). Alpine idles far lighter.
IMAGES = {"ubuntu": ("inspect-pi", 1024), "alpine": ("inspect-pi-alpine", 512)}


def proxmox_sandbox(image: str) -> SandboxEnvironmentSpec:
    tag, ram_mb = IMAGES[image]
    return SandboxEnvironmentSpec(
        "proxmox",
        ProxmoxSandboxEnvironmentConfig(
            sdn_config=OFFLINE,
            vms_config=(
                VmConfig(
                    vm_source_config=VmSourceConfig(existing_vm_template_tag=tag),
                    ram_mb=ram_mb,
                    vcpus=2,
                    # Clones keep the template's NIC unless this is set, and that NIC
                    # had internet while the template was built.
                    nics=(VmNicConfig(vnet_alias="offline"),),
                ),
            ),
        ),
    )


def dataset_id(dataset: str) -> str:
    """Accept either 'org/name' or a full https://huggingface.co/datasets/org/name link."""
    return dataset.split("huggingface.co/datasets/")[-1].strip("/")


@task
def hf_eval(
    dataset: str,
    input_field: str = "input",
    target_field: str = "target",
    split: str = "test",
    name: str | None = None,
    image: str = "ubuntu",
) -> Task:
    return Task(
        dataset=hf_dataset(
            dataset_id(dataset),
            split=split,
            name=name,
            sample_fields=FieldSpec(input=input_field, target=target_field),
        ),
        solver=pi_agent(),
        scorer=includes(),
        sandbox=proxmox_sandbox(image),
        message_limit=40,
    )


if __name__ == "__main__":
    assert dataset_id("https://huggingface.co/datasets/ai-safety-institute/AgentHarm") == "ai-safety-institute/AgentHarm"
    assert dataset_id("https://huggingface.co/datasets/org/name/") == "org/name"
    assert dataset_id("org/name") == "org/name"
    assert proxmox_sandbox("alpine").config.vms_config[0].ram_mb == 512
    print("ok")
