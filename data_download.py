from dotenv import load_dotenv
load_dotenv()

import kagglehub

# Download latest version
path = kagglehub.dataset_download("catdoglover/vietnam-legal-dataset")

print("Path to dataset files:", path)
