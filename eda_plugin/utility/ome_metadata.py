""" File to first try to make out own metadata """
import ome_types
import numpy as np
from datetime import datetime
import json
from typing import List
from pymm_eventserver.data_structures import MMSettings, PyImage, MMChannel


ome_model = ome_types.model
COLORS = ["white", "magenta", "green", "blue"]


class OME:
    """OME Metadata class based on ome_types

    This class can be used to generate OME metadata during an acquisition using the EDA plugin. The
    writer implemented uses this and the methods to generate the metadata as the images come in.
    """
    def __init__(self, ome=ome_model.OME, settings: MMSettings = None):
        # TODO: Make this version to be taken over from the setup.py file
        self.ome = ome(creator="LEB, EDA, V0.2.23")
        self.instrument_ref = ome_model.InstrumentRef(id="Instrument:0")
        # TODO: This we should get also in the settings
        self.stage_label = ome_model.StageLabel(
            name="Default", x=0.0, x_unit="µm", y=0.0, y_unit="µm"
        )
        if settings is None or settings.channels is None:
            self.channels = None
        else:
            self.internal_channels = []
            self.channels = self.channels_from_settings(settings.channels)

        self.settings = settings
        self.acquisition_date = datetime.now()
        self.image_size = [0, 0]
        self.max_indices = [1, 1, 1]
        self.planes = []
        self.tiff_data = []

    def add_plane_from_image(self, image: PyImage):
        """The units are hardcoded for now."""
        plane = ome_model.Plane(
            exposure_time=self.internal_channels[image.channel - 1]["exposure"],
            exposure_time_unit="ms",
            the_c=image.channel,
            the_z=image.z_slice,
            the_t=image.timepoint,
            delta_t=image.time,
            delta_t_unit="ms",
            position_x=0.0,
            position_x_unit="µm",
            position_y=0.0,
            position_y_unit="µm",
            position_z=0.0,
            position_z_unit="µm",
        )
        tiff = ome_model.TiffData(
            first_c=image.channel,
            first_t=image.timepoint,
            first_z=image.z_slice,
            ifd=len(self.planes),
            plane_count=1,
        )
        self.image_size = image.raw_image.shape
        self.max_indices = [
            max(self.max_indices[0], image.channel + 1),
            max(self.max_indices[1], image.timepoint + 1),
            max(self.max_indices[2], image.z_slice + 1),
        ]
        self.planes.append(plane)
        self.tiff_data.append(tiff)

    def finalize_metadata(self):
        """No more images to be expected, set the values for all images received so far."""
        pixels = self.pixels_after_acqusition()
        images = [
            ome_model.Image(id="Image:0", pixels=pixels, acquisition_date=self.acquisition_date)
        ]
        self.ome.images = images

    def pixels_after_acqusition(self) -> ome_model.Pixels:
        """Generate the Pixels instance after all images where acquired and received."""
        pixels = ome_model.Pixels(
            id="Pixels:0",
            dimension_order=self.settings.acq_order,
            size_c=self.max_indices[0],
            size_t=self.max_indices[1],
            size_z=self.max_indices[2],
            size_x=self.image_size[0],
            size_y=self.image_size[1],
            type=ome_model.simple_types.PixelType("uint16"),
            big_endian=False,
            physical_size_x=1.0,
            physical_size_x_unit=ome_model.simple_types.UnitsLength("µm"),
            physical_size_y=1.0,
            physical_size_y_unit=ome_model.simple_types.UnitsLength("µm"),
            physical_size_z=0.5,
            physical_size_z_unit=ome_model.simple_types.UnitsLength("µm"),
            channels=self.channels,
            planes=self.planes,
            tiff_data_blocks=self.tiff_data,
        )
        return pixels

    def init_from_settings(self, settings: MMSettings):
        """Initialize OME from MMSettings translated from Micro-Manager settings from java."""
        self.settings = settings
        self.ome.channels = self.ome_channels(settings.channels)
        self.ome.instrument = self.instrument_from_settings(settings.microscope)

    def instrument_from_settings(self, microscope):
        """Generate the instrument from the information received from Micro-Manager."""
        instrument = ome_model.Instrument(
            id="Instrument:0",
            detectors=[self.detector_from_settings(microscope.detector)],
            microscope=self.microscope_from_settings(microscope),
        )
        return instrument

    def channels_from_settings(self, channels: List[MMChannel]):
        """Generate the channels from the channel information received from Micro-Manager."""
        print(channels)
        ome_channels = []
        for idx, channel in enumerate(channels):
            ome_channel = ome_model.Channel(
                id="Channel:0:" + str(idx),
                name=channels[channel]["name"],
                color=ome_model.simple_types.Color(
                    channels[channel]["color"]
                ),  # TODO implement to take colors over
                samples_per_pixel=1,  # TODO check if this is correct
            )
            ome_channels.append(ome_channel)
            self.internal_channels.append({"exposure": channels[channel]["exposure"]})
        return ome_channels

    def detector_from_settings(self, detector):
        """Generate the detector from the information received from Micro-Manager."""
        return ome_model.Detector(
            id=detector.id,
            manufacturer=detector.manufacturer,
            model=detector.model,
            serial_number=detector.serial_number,
            offset=detector.offset,
        )

    def microscope_from_settings(self, microscope):
        """ Generate the microscope from the information received from Micro-Manager."""
        return ome_model.Microscope(manufacturer=microscope.manufacturer, model=microscope.model)


if __file__ == "__main__":


    metadata_string = '{"PositionName":"Default","PixelSizeAffine":"AffineTransform[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]","UserData":{"PseudoChannel-useChannels":"Off","PseudoChannel-useSlices":"Off","PseudoChannel-Slices":"1","PseudoChannel-Channels":"1"},"ReceivedTime":"2022-08-12 15:59:07.413 +0200","ROI":"java.awt.Rectangle[x=0,y=0,width=512,height=512]","BitDepth":"16","ElapsedTimeMs":"419.0","ZPositionUm":"0.0","Binning":"1","ExposureMs":"100.0","ScopeData":{"Z-Description":"Demo stage driver","Camera-PixelType":"16bit","Camera-Binning":"1","Core-Shutter":"Shutter","Camera-FastImage":"0","Z-Name":"DStage","Camera-SimulateCrash":"","Emission-Name":"DWheel","Camera-TransposeMirrorX":"0","Camera-TransposeMirrorY":"0","Shutter-State":"0","Camera-Mode":"Artificial Waves","Core-AutoShutter":"1","Z-Position":"0.0000","Camera-UseExposureSequences":"No","Dichroic-State":"0","Dichroic-Name":"DWheel","Path-Description":"Demo light-path driver","Path-Name":"DLightPath","Camera-Description":"Demo Camera Device Adapter","Dichroic-Description":"Demo filter wheel driver","Camera-ReadNoise (electrons)":"2.5000","Camera-RotateImages":"0","Dichroic-HubID":"","Camera-BitDepth":"16","Camera-DisplayImageNumber":"0","Camera-FractionOfPixelsToDropOrSaturate":"0.0020","Core-ChannelGroup":"Channel","Camera-AsyncPropertyLeader":"","Path-HubID":"","Excitation-Name":"DWheel","Camera-OnCameraCCDYSize":"512","Core-ImageProcessor":"","Core-Camera":"Camera","Camera-CameraID":"V1.0","XY-TransposeMirrorX":"0","Objective-State":"1","XY-TransposeMirrorY":"0","XY-Name":"DXYStage","Camera-MultiROIFillValue":"0","Camera-AsyncPropertyDelayMS":"2000","Excitation-Description":"Demo filter wheel driver","Camera-SaturatePixels":"0","Autofocus-Description":"Demo auto-focus adapter","Camera-Name":"DCam","Excitation-HubID":"","Camera-TransposeXY":"0","Camera-CCDTemperature":"0.0000","Camera-Gain":"0","Autofocus-HubID":"","Shutter-HubID":"","Camera-TestProperty1":"0.0000","Camera-DropPixels":"0","Camera-TestProperty2":"0.0000","Camera-TestProperty3":"0.0000","Autofocus-Name":"DAutoFocus","Camera-TestProperty4":"0.0000","Z-UseSequences":"No","Camera-TestProperty5":"0.0000","Camera-TestProperty6":"0.0000","Emission-ClosedPosition":"0","Shutter-Description":"Demo shutter driver","Core-Initialize":"1","XY-HubID":"","Emission-State":"0","Emission-Description":"Demo filter wheel driver","Core-AutoFocus":"Autofocus","Z-HubID":"","Camera-CameraName":"DemoCamera-MultiMode","Objective-Label":"Nikon 10X S Fluor","Camera-ScanMode":"1","Camera-TransposeCorrection":"0","Camera-AsyncPropertyFollower":"","Core-TimeoutMs":"5000","Objective-HubID":"","Dichroic-ClosedPosition":"0","Shutter-Name":"DShutter","XY-Description":"Demo XY stage driver","Camera-Exposure":"100.00","Core-Galvo":"","Camera-MaximumExposureMs":"10000.0000","Camera-ReadoutTime":"0.0000","Camera-Photon Conversion Factor":"1.0000","Dichroic-Label":"400DCLP","Emission-HubID":"","Camera-HubID":"","Camera-Photon Flux":"50.0000","Camera-TriggerDevice":"","Excitation-State":"0","Core-XYStage":"XY","Path-Label":"State-0","Excitation-ClosedPosition":"0","Camera-AllowMultiROI":"0","Emission-Label":"Chroma-HQ700","Objective-Name":"DObjective","Excitation-Label":"Chroma-HQ570","Core-SLM":"","Path-State":"0","Objective-Trigger":"-","Camera-CCDTemperature RO":"0.0000","Camera-Offset":"0","Core-Focus":"Z","Camera-OnCameraCCDXSize":"512","Objective-Description":"Demo objective turret driver","Camera-StripeWidth":"1.0000"},"XPositionUm":"0.0","PixelSizeUm":"1.0","Class":"class org.micromanager.data.internal.DefaultMetadata","Camera":"Camera","UUID":"798e1008-c618-4ca8-b3f5-0c0212a858aa","YPositionUm":"0.0"}'
    metadata_dict = json.loads(metadata_string)

    print(json.dumps(metadata_dict, indent=4))

    settings = MMSettings(None)