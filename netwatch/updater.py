import subprocess, sys, os

def main():
    print("Updating netwatchv2...")
    subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "git+https://github.com/assyaref/netwatchV2.git"], check=False)
    print("Done.")

if __name__ == "__main__":
    main()