##Luci ClusterPlot Service
***
### What does it do?
The service connects to Qua-viewer via Luci. It reads the scenario display in Qua viewer and process with the geojson data using luciplot.py. The plot contains a collection of nine images of neighbourhood detection using different parameter set using DBSCAN. The plot is displayed in the right panel in qua-viewer
### How to run it?
simply run plot_service.py

luciplot.py contains plotting process where the image is stored locally at data/luci_test.png. You can change the directory of the generated image. 