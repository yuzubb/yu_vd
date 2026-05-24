import subprocess
import sys

print("BCSFEをインストールします...")
subprocess.run(f"{sys.executable} -m pip install --upgrade pip", shell=True)
subprocess.run(f"{sys.executable} -m pip install bcsfe", shell=True)
print("\n完了")
input("Enterで終了")