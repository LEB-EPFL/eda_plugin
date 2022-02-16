""" Script to download the example data."""
import os


def download_data(path: str = None):
    if path is None:
        path = os.path.join(
            os.path.abspath(os.path.join(__file__, "..", "..")), "examples", "data"
        )
    os.chdir(path)
    print(f"Copying example data to {path}")
    os.system("zenodo_get 10.5281/zenodo.6102930")


if __name__ == "__main__":
    download_data()
