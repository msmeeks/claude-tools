# Deploy Ollama on AWS EC2

Runs Ollama + Caddy on an EC2 instance. Caddy handles HTTPS via Let's Encrypt;
Ollama is bound to `127.0.0.1` so it is never directly reachable from the internet.

## Prerequisites

- AWS account, `aws` CLI configured
- A domain name and Route 53 (or any DNS) control
- EC2 key pair for SSH

## Instance sizing

| Model | Instance type | Notes |
|---|---|---|
| llama3.1:8b | `t3.xlarge` (16 GB RAM) | CPU-only; ~15 tok/s |
| qwen2.5-coder:7b | `t3.xlarge` | CPU-only |
| qwen2.5-coder:32b | `g4dn.xlarge` (NVIDIA T4) | GPU required |

## Launch steps

```bash
# 1. Generate your Caddy password hash locally
caddy hash-password --plaintext YOUR_STRONG_PASSWORD
# note the output: $2a$14$...

# 2. Edit the user-data script
cp ec2-user-data.sh.example ec2-user-data.sh
# Replace REPLACE_YOUR_DOMAIN.example.com with your domain
# Replace REPLACE_CADDY_HASH with the hash from step 1

# 3. Launch the instance
aws ec2 run-instances \
  --image-id ami-0c7217cdde317cfec \   # Ubuntu 22.04 LTS in us-east-1; check for latest
  --instance-type t3.xlarge \
  --key-name YOUR_KEY_PAIR \
  --security-group-ids sg-REPLACE \
  --user-data file://ec2-user-data.sh \
  --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":60}}]'

# 4. Security group rules (minimum):
#    Inbound port 443 from YOUR_IP/32 only
#    Inbound port 22  from YOUR_IP/32 only
#    NO inbound rule for port 11434

# 5. Add DNS A record:
#    your-domain.com → <EC2 public IP>

# 6. Wait ~5 minutes for user-data to complete, then pull a model:
ssh ubuntu@<EC2_IP> "sudo ollama pull qwen2.5-coder:7b"
```

## Configure the client

Same as fly.io — see `deploy/fly/README.md` "Configure the client" section.
Replace the fly.io domain with your EC2 domain.

## Cost management

Stop the instance when not in use:
```bash
aws ec2 stop-instances --instance-ids i-REPLACE
aws ec2 start-instances --instance-ids i-REPLACE
```

The Elastic IP stays allocated to avoid a domain change, but compute stops billing.
Use a `t3.xlarge` spot instance for ~70% cost reduction if interruptions are tolerable.

## Secrets

Never put plaintext passwords in user-data scripts committed to git. The
`ec2-user-data.sh.example` file uses placeholder strings. The filled-in
`ec2-user-data.sh` is gitignored — verify with `git status` before committing.

For production use, pull secrets from AWS SSM Parameter Store at boot instead
of hardcoding them in user-data.
