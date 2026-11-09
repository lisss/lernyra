#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KEY_PATH="${KEY_PATH:-$HOME/.ssh/jobify-ec2}"
KEY_NAME="${KEY_NAME:-lernyra}"
REGION="${AWS_DEFAULT_REGION:-us-east-1}"
INSTANCE_TYPE="${INSTANCE_TYPE:-t3.micro}"
REPO_URL="${REPO_URL:-https://github.com/lisss/lernyra.git}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

if [[ ! -f "$KEY_PATH" || ! -f "$KEY_PATH.pub" ]]; then
  echo "Missing $KEY_PATH — generate with: ssh-keygen -t ed25519 -f ~/.ssh/jobify-ec2 -N ''"
  exit 1
fi

if [[ -z "${AWS_ACCESS_KEY_ID:-}" || -z "${AWS_SECRET_ACCESS_KEY:-}" ]]; then
  echo "Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY first."
  exit 1
fi

cp "$KEY_PATH.pub" "$TMP/lernyra-ec2.pub"

aws() {
  docker run --rm \
    -e AWS_ACCESS_KEY_ID \
    -e AWS_SECRET_ACCESS_KEY \
    -e AWS_DEFAULT_REGION="$REGION" \
    -e AWS_SESSION_TOKEN \
    -v "$TMP:/work" \
    -w /work \
    amazon/aws-cli:latest "$@"
}

echo "==> Who am I"
aws sts get-caller-identity

echo "==> Import key pair (idempotent)"
if ! aws ec2 describe-key-pairs --key-names "$KEY_NAME" >/dev/null 2>&1; then
  aws ec2 import-key-pair \
    --key-name "$KEY_NAME" \
    --public-key-material "fileb:///work/lernyra-ec2.pub"
else
  echo "Key pair $KEY_NAME already exists"
fi

echo "==> Security group"
SG_NAME="lernyra-web"
VPC_ID="$(aws ec2 describe-vpcs --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId' --output text)"
SG_ID="$(aws ec2 describe-security-groups --filters "Name=group-name,Values=$SG_NAME" "Name=vpc-id,Values=$VPC_ID" --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || true)"
if [[ -z "$SG_ID" || "$SG_ID" == "None" ]]; then
  SG_ID="$(aws ec2 create-security-group --group-name "$SG_NAME" --description "lernyra HTTP/SSH" --vpc-id "$VPC_ID" --query GroupId --output text)"
  MYIP="$(curl -4 -fsS https://checkip.amazonaws.com | tr -d '[:space:]')"
  aws ec2 authorize-security-group-ingress --group-id "$SG_ID" --ip-permissions \
    "IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges=[{CidrIp=0.0.0.0/0,Description=ssh-ci-and-admin}]" \
    "IpProtocol=tcp,FromPort=80,ToPort=80,IpRanges=[{CidrIp=0.0.0.0/0,Description=http}]" \
    "IpProtocol=tcp,FromPort=443,ToPort=443,IpRanges=[{CidrIp=0.0.0.0/0,Description=https}]"
fi
echo "SG=$SG_ID"

echo "==> Latest Ubuntu 24.04 AMI"
AMI="$(aws ec2 describe-images \
  --owners 099720109477 \
  --filters "Name=name,Values=ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*" "Name=state,Values=available" \
  --query 'sort_by(Images,&CreationDate)[-1].ImageId' --output text)"
if [[ -z "$AMI" || "$AMI" == "None" ]]; then
  AMI="$(aws ec2 describe-images \
    --owners 099720109477 \
    --filters "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-noble-24.04-amd64-server-*" "Name=state,Values=available" \
    --query 'sort_by(Images,&CreationDate)[-1].ImageId' --output text)"
fi
echo "AMI=$AMI"

cat > "$TMP/user-data.sh" <<EOF
#!/bin/bash
set -euxo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y ca-certificates curl git
curl -fsSL https://get.docker.com | sh
usermod -aG docker ubuntu
mkdir -p /opt/lernyra
git clone --depth 1 ${REPO_URL} /opt/lernyra || true
chown -R ubuntu:ubuntu /opt/lernyra
EOF

echo "==> Launch instance"
INSTANCE_ID="$(aws ec2 run-instances \
  --image-id "$AMI" \
  --instance-type "$INSTANCE_TYPE" \
  --key-name "$KEY_NAME" \
  --security-group-ids "$SG_ID" \
  --count 1 \
  --user-data file:///work/user-data.sh \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=lernyra}]" \
  --query 'Instances[0].InstanceId' --output text)"
echo "INSTANCE_ID=$INSTANCE_ID"

echo "==> Wait until running"
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID"

echo "==> Elastic IP"
ALLOC="$(aws ec2 allocate-address --domain vpc --query AllocationId --output text)"
aws ec2 associate-address --instance-id "$INSTANCE_ID" --allocation-id "$ALLOC" >/dev/null
PUBLIC_IP="$(aws ec2 describe-addresses --allocation-ids "$ALLOC" --query 'Addresses[0].PublicIp' --output text)"
echo "PUBLIC_IP=$PUBLIC_IP"

DOMAIN="${PUBLIC_IP}.sslip.io"
OUT="$ROOT/deploy/.provisioned.env"
cat > "$OUT" <<EOF
EC2_HOST=$PUBLIC_IP
EC2_USER=ubuntu
DOMAIN=$DOMAIN
IMAGE=ghcr.io/lisss/lernyra:latest
INSTANCE_ID=$INSTANCE_ID
ALLOCATION_ID=$ALLOC
REGION=$REGION
EOF
chmod 600 "$OUT"

echo ""
echo "Wrote $OUT"
echo "SSH: ssh -i $KEY_PATH ubuntu@$PUBLIC_IP"
echo "URL once up: https://$DOMAIN"
echo ""
echo "Next: wait ~2 min for user-data, then run:"
echo "  ./deploy/finish-remote.sh"
