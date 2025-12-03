# Colima Profile Management

## Available Profiles

1. **default** - 8 CPUs, 16GB RAM (general development)
2. **max** - 10 CPUs, 24GB RAM (heavy testing)

Config locations: ~/.config/colima/{profile-name}/colima.yaml

## Basic Usage

Start default profile:
`colima start`

Start max profile for heavy testing:
`colima start -p max`

List all profiles:
`colima list`

## Switch Between Profiles

Stop current and start max:
`colima stop && colima start -p max`

Back to default:
`colima stop -p max && colima start`

## Profile-Specific Commands

Stop a specific profile:
`colima stop -p max`

Delete a profile:
`colima delete -p max`

SSH into a specific profile:
`colima ssh -p max`

## Testing Workflow

Heavy testing with max profile:

```bash
colima stop
colima start -p max
bash management/tests/test-install-wsl-docker.sh
colima stop -p max
colima start
```

## One-Time Overrides

Temporary resource override (doesn't save to config):
`colima start --cpu 10 --memory 24`

## Important Notes

- Only one profile can run at a time
- Each profile has its own VM, containers, and storage
- Containers in one profile won't be visible in another
- Both use the same Docker context when active
