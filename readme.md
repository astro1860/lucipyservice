##Luci ClusterPlot Service
***
### What does it do?
The service connects to Qua-viewer via Luci. It reads the scenario display in Qua viewer and process with the geojson data using luciplot.py. The plot contains a collection of nine images of neighbourhood detection using different parameter set using DBSCAN. The plot is displayed in the right panel in qua-viewer
### Set up
This project requires python 3+

Python depedencies include:numpy,shapely,matplotlib,sklearn,scipy,descartes

simply run in your terminal:
```
pip3 install numpy
pip3 install shapely
pip3 install matplotlib
pip3 install sklearn
pip3 install scipy
pip3 install descartes
```
### How to run it?
Step1. simply run plot_service.py

luciplot.py contains plotting process where the image is stored locally at data/luci_test.png. You can change the directory of the generated image. 

Step2. go to http://qua-kit.ethz.ch/viewer. you can either select scenario hangxingeotest or read Geojson from file choose from geometry. The buidling will only be rendered and clustered if the properties setting in geojson is not "static" and the geometry type is either polygon or multipolygon.


Step3. Run Service
Go to services and choose "hangxin" from remote service to run. You should be able to see an image displayed at INFO(right) panel

### Todo
Rendering but not clustering the 'static' buildings. 
