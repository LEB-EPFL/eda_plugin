from eda_plugin.utility.ome_metadata import OME
import numpy as np
import os
import tifffile
from pymm_eventserver.data_structures import PyImage
# from tests.utility.test_writers import test_clean_up



def main():
    try:
        test_ome_from_settings()
        test_writing_data()
    finally:
        pass
        # test_clean_up()


def test_ome_from_settings(MMSettings_mock):
    ome = OME(settings=MMSettings_mock)


def test_writing_data(MMSettings_mock):
    test_data = (np.random.random([50, 2, 512, 512]) * 255).astype(np.uint8)
    ome = OME(settings=MMSettings_mock)
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
