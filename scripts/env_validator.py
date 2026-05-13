#!/usr/bin/env python3
from pathlib import Path


def parse_env_file(file_path):
    """Parse an environment file and return a dictionary of keys and values."""
    try:
        with Path.open(file_path, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        return {}

    env_vars = {}
    for line in lines:
        clean_line = line.strip()
        if not clean_line or clean_line.startswith('#'):
            continue

        if '=' in clean_line:
            key, value = clean_line.split('=', 1)
            env_vars[key.strip()] = value.strip()

    return env_vars


def sync_env_files(dist_file, env_file):
    """Synchronize .env with .env.dist, keeping .env values where available."""
    # Parse both files
    dist_content = []
    env_vars = {}

    # Read .env.dist content
    try:
        with Path.open(dist_file, 'r') as f:
            dist_content = f.readlines()
    except FileNotFoundError:
        print(f'Error: {dist_file} not found.')
        return

    # Get existing .env values
    env_vars = parse_env_file(env_file)

    # Create new .env content based on .env.dist structure
    new_env_content = []
    keys_processed = set()

    # Process each line in .env.dist
    for line in dist_content:
        # Keep comments and empty lines as they are
        if not line.strip() or line.strip().startswith('#'):
            new_env_content.append(line)
            continue

        # Handle variable lines
        if '=' in line:
            key, default_value = line.split('=', 1)
            key = key.strip()
            default_value = default_value.strip()
            keys_processed.add(key)

            # If key exists in .env, use that value, otherwise prompt for new value
            if key in env_vars:
                value = env_vars[key]
                new_env_content.append(f'{key}={value}\n')
            else:
                user_input = input(f'Enter value for {key} (default: {default_value}): ').strip()
                value = user_input if user_input else default_value
                new_env_content.append(f'{key}={value}\n')

    # Check for keys in .env that aren't in .env.dist
    extra_keys = set(env_vars.keys()) - keys_processed
    if extra_keys:
        print('\nThe following keys exist in .env but not in .env.dist and will be removed:')
        for key in extra_keys:
            print(f'  - {key}')
        input('Press Enter to continue...')

    # Write the new .env file
    with Path.open(env_file, 'w') as f:
        f.writelines(new_env_content)

    print(f'\nSuccessfully synchronized {env_file} with the structure of {dist_file}.')


def main():
    """Main function."""
    # File paths
    dist_file = '.env.dist'
    env_file = '.env'

    # Create .env file if it doesn't exist
    try:
        Path.open(env_file, 'a').close()
    except OSError:
        print(f'Error: Unable to create or access {env_file}.')
        return

    # Synchronize the files
    sync_env_files(dist_file, env_file)

    print('Validation and synchronization complete!')


if __name__ == '__main__':
    main()
