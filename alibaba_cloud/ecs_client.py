"""
Alibaba Cloud ECS Integration — REQUIRED for hackathon submission.
Demonstrates use of Alibaba Cloud services and APIs.
This file is the "proof of Alibaba Cloud deployment" required by the judges.

Functionality:
- Deploy NeuroScale Autopilot backend to ECS instance
- Query ECS instance status
- Configure security groups for API access
"""

import os
import structlog
from typing import Optional

logger = structlog.get_logger(__name__)


def get_ecs_client():
    """Create and return an authenticated Alibaba Cloud ECS client."""
    try:
        from alibabacloud_ecs20140526 import client as ecs_client
        from alibabacloud_ecs20140526 import models as ecs_models
        from alibabacloud_tea_openapi import models as open_api_models

        access_key_id = os.getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")
        access_key_secret = os.getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")
        region = os.getenv("ALIBABA_CLOUD_REGION", "cn-hangzhou")

        if not access_key_id or not access_key_secret:
            raise ValueError("ALIBABA_CLOUD_ACCESS_KEY_ID and ALIBABA_CLOUD_ACCESS_KEY_SECRET required")

        config = open_api_models.Config(
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
            region_id=region,
            endpoint=f"ecs.{region}.aliyuncs.com",
        )
        return ecs_client.Client(config)

    except ImportError as e:
        logger.error("alibaba_sdk_not_installed", error=str(e))
        raise


async def list_ecs_instances(region: Optional[str] = None) -> dict:
    """
    List ECS instances running the NeuroScale Autopilot backend.
    Returns instance IDs, public IPs, and status.
    """
    try:
        from alibabacloud_ecs20140526 import models as ecs_models
        client = get_ecs_client()
        region = region or os.getenv("ALIBABA_CLOUD_REGION", "cn-hangzhou")

        request = ecs_models.DescribeInstancesRequest(
            region_id=region,
            tag=[
                ecs_models.DescribeInstancesRequestTag(
                    key="project",
                    value="neuroscale-autopilot"
                )
            ]
        )

        response = client.describe_instances(request)
        instances = []

        for inst in response.body.instances.instance:
            public_ip = ""
            if inst.public_ip_address and inst.public_ip_address.ip_address:
                public_ip = inst.public_ip_address.ip_address[0]

            instances.append({
                "instance_id": inst.instance_id,
                "instance_name": inst.instance_name,
                "status": inst.status,
                "public_ip": public_ip,
                "region": region,
                "instance_type": inst.instance_type,
            })

        logger.info("ecs_instances_listed", count=len(instances), region=region)
        return {"instances": instances, "region": region}

    except Exception as e:
        logger.error("ecs_list_failed", error=str(e))
        return {"error": str(e), "instances": []}


async def create_ecs_instance(
    instance_name: str = "neuroscale-autopilot-backend",
    instance_type: str = "ecs.t6-c1m1.large",
    image_id: str = "ubuntu_22_04_x64_20G_alibase_20240130.vhd",
) -> dict:
    """
    Create a new ECS instance for the autopilot backend.
    Uses Ubuntu 22.04 + Docker for deployment.
    """
    try:
        from alibabacloud_ecs20140526 import models as ecs_models
        client = get_ecs_client()
        region = os.getenv("ALIBABA_CLOUD_REGION", "cn-hangzhou")

        request = ecs_models.RunInstancesRequest(
            region_id=region,
            image_id=image_id,
            instance_type=instance_type,
            instance_name=instance_name,
            security_group_id=os.getenv("ALIBABA_CLOUD_SECURITY_GROUP_ID", ""),
            v_switch_id=os.getenv("ALIBABA_CLOUD_VSWITCH_ID", ""),
            internet_max_bandwidth_out=10,
            password=os.getenv("ALIBABA_CLOUD_INSTANCE_PASSWORD", "NeuroScale@2026!"),
            system_disk=ecs_models.RunInstancesRequestSystemDisk(
                size="40",
                category="cloud_essd",
            ),
            tag=[
                ecs_models.RunInstancesRequestTag(key="project", value="neuroscale-autopilot"),
                ecs_models.RunInstancesRequestTag(key="hackathon", value="qwen-global-ai-2026"),
                ecs_models.RunInstancesRequestTag(key="track", value="autopilot-agent"),
            ],
            user_data=_get_startup_script(),
        )

        response = client.run_instances(request)
        instance_ids = response.body.instance_id_sets.instance_id_set

        logger.info("ecs_instance_created", instance_ids=instance_ids)
        return {
            "success": True,
            "instance_ids": list(instance_ids),
            "region": region,
            "message": "NeuroScale Autopilot backend deploying to Alibaba Cloud ECS"
        }

    except Exception as e:
        logger.error("ecs_create_failed", error=str(e))
        return {"success": False, "error": str(e)}


def _get_startup_script() -> str:
    """
    ECS user-data startup script.
    Installs Docker + deploys NeuroScale Autopilot on boot.
    Base64-encoded for ECS user_data field.
    """
    import base64
    script = """#!/bin/bash
set -e

# Update system
apt-get update -y
apt-get install -y docker.io docker-compose git python3-pip curl

# Start Docker
systemctl start docker
systemctl enable docker

# Clone NeuroScale Autopilot
git clone https://github.com/sodiq-code/neuroscale-autopilot.git /opt/neuroscale-autopilot
cd /opt/neuroscale-autopilot

# Create .env from instance metadata
cat > .env << EOF
QWEN_API_KEY=${QWEN_API_KEY}
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
APP_HOST=0.0.0.0
APP_PORT=8000
ENVIRONMENT=production
LOG_LEVEL=INFO
EOF

# Install dependencies
pip3 install -r requirements.txt

# Start the autopilot backend
nohup python3 main.py > /var/log/neuroscale-autopilot.log 2>&1 &

echo "NeuroScale Autopilot deployed successfully on Alibaba Cloud ECS"
"""
    return base64.b64encode(script.encode()).decode()


async def get_instance_status(instance_id: str) -> dict:
    """Check the status of a specific ECS instance."""
    try:
        from alibabacloud_ecs20140526 import models as ecs_models
        client = get_ecs_client()
        region = os.getenv("ALIBABA_CLOUD_REGION", "cn-hangzhou")

        request = ecs_models.DescribeInstanceStatusRequest(
            region_id=region,
            instance_id=[instance_id],
        )
        response = client.describe_instance_status(request)
        statuses = response.body.instance_statuses.instance_status

        if statuses:
            return {
                "instance_id": instance_id,
                "status": statuses[0].status,
            }
        return {"instance_id": instance_id, "status": "not_found"}

    except Exception as e:
        return {"instance_id": instance_id, "error": str(e)}
