from .cli import main

# Guard so process-pool workers (spawned on macOS) do not re-run the CLI.
if __name__ == "__main__":
    main()
