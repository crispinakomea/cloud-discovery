# Terraform infrastructure for Azure

This repository contains Terraform configurations that provision Azure infrastructure split into focused modules/areas. It is organized for local development and testing; several directories include local state files (terraform.tfstate). Consider migrating to a remote backend (eg. Azure Storage Account) for team use.

Repository layout

- `acr/` - Azure Container Registry related resources
- `compute/` - VM/compute resources and related RBAC role definitions
- `environment/` - shared environment-level resources
- `vm/` - Virtual Machines and VM-specific modules
- `storage/` - Storage, Cosmos DB, Event Hub, Service Bus, etc.
- `others.txt` - miscellaneous notes

Each folder is a separate Terraform root module containing its own `main.tf`, `provider.tf`, variable and data definitions. Some folders contain `terraform.tfstate` and `terraform.tfstate.backup` (local state) — be careful when running commands.

Prerequisites

- Terraform (recommended 1.5.x or later)
- Azure CLI (az)
- An Azure subscription and appropriate permissions to create resources

Quickstart (PowerShell)

1. Install/verify tooling

- Verify Terraform:
  terraform -version

- Verify Azure CLI and sign in:
  az login
  az account set --subscription "<your-subscription-id-or-name>"

2. Initialize a module

Open a PowerShell prompt in the module directory you want to manage, for example `compute`:

  cd compute
  terraform init

3. Validate and preview changes

  terraform fmt -recursive
  terraform validate
  terraform plan -out plan.tfplan

4. Apply changes

  terraform apply "plan.tfplan"

5. Destroy (when needed)

  terraform destroy

Notes and best practices

- Do not keep local `terraform.tfstate` files in a shared repository for team workflows. Configure a remote backend (Azure Storage Account + container + blob lock) and move state there.
- Use variables and a `terraform.tfvars` file or environment variables to avoid committing secrets.
- Review `provider.tf` in each module to confirm subscription and tenant configuration.
- Commit only .tf files and exclude local state and .terraform directories via `.gitignore`.

Suggested .gitignore entries

  .terraform/
  terraform.tfstate
  terraform.tfstate.backup
  *.tfvars

Contact / Maintainers

If you need help maintaining these configurations, open an issue or contact the repository owner.
