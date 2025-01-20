# new conda environment
conda create -n docking python=3.9
conda activate docking

# clone boltz-1 repo
git clone https://github.com/boltz-1/boltz-1.git
cd boltz-1

# install pytorch and pytorch geometric
conda install pytorch torchvision torchaudio -c pytorch
conda install pyg -c pyg

# install other dependencies
pip install -r requirements.txt