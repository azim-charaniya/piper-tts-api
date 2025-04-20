# Dockerfile
# This Dockerfile builds a container for the Piper TTS API using a Conda environment.
# It follows best practices from [docs.conda.io](https://docs.conda.io/docs/user-guide/tasks/manage-environments.html) for managing isolated environments.
# Based on [www.anaconda.com](https://www.anaconda.com/docs/tools/working-with-conda/environments) for isolation and reproducibility.

FROM continuumio/miniconda3

# Set the working directory
WORKDIR /app

# Copy requirements file and create Conda environment
COPY environment.yml .

# Create and activate the Conda environment, then install dependencies
# As per [tech.wayne.edu](https://tech.wayne.edu/kb/high-performance-computing/hpc-tutorials/500368), this ensures isolation
RUN conda env create -f environment.yml && \
    conda init bash && \
    echo "source activate tts-api-env" >> ~/.bashrc  # Activate the environment on container start

# install ffmpeg
RUN apt-get update && apt-get install -y ffmpeg

# Copy the rest of the application code
COPY . .

# Expose the port
EXPOSE 17100

# Command to run the app: Source the Conda environment and start the app
# Using [stackoverflow.com](https://stackoverflow.com/questions/20081338/how-to-activate-an-anaconda-environment) for activation
CMD ["/bin/bash", "-c", "source /opt/conda/etc/profile.d/conda.sh && conda activate tts-api-env && python app.py"]
