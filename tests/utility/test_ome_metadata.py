from pymm_eventserver.data_structures import MMSettings
from eda_plugin.utility.ome_metadata import OME
import numpy as np
import os
import tifffile
from pymm_eventserver.data_structures import PyImage
from test_writers import test_clean_up

settings = MMSettings()
config = "488"
settings.channels[config] = {
    "name": config,
    "color": [255, 255, 255],
    "use": True,
    "exposure": 100,
    "z_stack": False,
}
config = "561"
settings.channels[config] = {
    "name": config,
    "color": [255, 0, 0],
    "use": True,
    "exposure": 100,
    "z_stack": False,
}
settings.n_channels = 2


def main():
    try:
        test_ome_from_settings()
        test_writing_data()
    finally:
        test_clean_up()


def test_ome_from_settings():
    ome = OME(settings=settings)


def test_writing_data():
    test_data = (np.random.random([50, 2, 512, 512]) * 255).astype(np.uint8)
    ome = OME(settings=settings)
    for timepoint, frames in enumerate(test_data):
        for channel, frame in enumerate(frames):
            time = timepoint * 300 + channel * 150
            image = PyImage(frame, None, timepoint + 1, channel + 1, 1, time)
            ome.add_plane_from_image(image)
    ome.finalize_metadata()
    xml_ome = ome.ome.to_xml()
    tifffile.imwrite(
        os.path.dirname(os.path.dirname(__file__)) + "/data/FOV.ome.tif",
        test_data,
        description=xml_ome.encode(encoding="UTF-8", errors="strict"),
    )


if __name__ == "__main__":
    main()
