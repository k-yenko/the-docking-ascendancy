# new conda environment
conda create -n docking python=3.11
conda activate docking

# install boltz-1
pip install boltz

# install pytorch
conda install pytorch torchvision -c pytorch -y
conda install -c conda-forge pymol-open-source -y

# pyg dependencies
conda install -c conda-forge pytorch-scatter pytorch-sparse pytorch-cluster pytorch-spline-

# pyg
conda install -c conda-forge pytorch-geometric

# install other dependencies
pip install -r requirements.txt

# Set environment variables
echo 'export PYTORCH_ENABLE_MPS_FALLBACK=1' >> ~/.bashrc
echo 'export CUDA_VISIBLE_DEVICES=""' >> ~/.bashrc
