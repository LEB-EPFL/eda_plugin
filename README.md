# Event-driven acquisition (EDA)

'event-driven-acquisition' is a Python library for advanced microscope control routines to enable
acquisitions to react to specific biological events of interest.

More information on the project it was first used on can be found in the [bioRxiv article](https://www.biorxiv.org/content/10.1101/2021.10.04.463102v1).

## Components of EDA


### Analyzers
Analyzers receive an image or images from the microscope. Their task is to reduce the information in
these images to a single or a set of parameters. These parameters are passed on to interpreters.

### Interpreters
An interpreter receives parameters from an analyzer and uses these to take a decision for how to
proceed with acquisition. This decision is passed on to an actuator. The interpretation can for
example take into account the temporal context of results from the analyzer.

### Actuators
The responsibility of an actuator is both to handle start/stop of acquisitions and to apply the
decisions from an interpreter to the ongoing acquisition.


## Installing Event-driven acquisition

1) Install the latest version of [micro-manager2.0](https://micro-manager.org/wiki/Micro-Manager_Nightly_Builds)
2) Download this repository
3) Install the required dependencies
4) Run micro-manager with the zmq server ([pycromanager installation](https://github.com/micro-manager/pycro-manager/blob/master/README.md))
5) Run the PythonEventServer from Plugins -> Developer Tools -> Python Event Server
6) Run 'python -m examples.main' from the home directory of the package.