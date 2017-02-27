import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import json
import shapely
from shapely.geometry import Polygon
from sklearn import cluster,metrics
from scipy.spatial import distance
from descartes import PolygonPatch

def luciplot(data):

	centroid_alles = []
	polygon_alles = []
	points_alles = []
	for i,feature in enumerate(data['features']):
	    if 'static' in feature['properties']:
	        ifdynamic = False
	    else:
	        ifdynamic = True
	#     print (ifstatic)
	    if (feature['geometry']["type"]=="MultiPolygon" or feature['geometry']["type"]=="Polygon") and ifdynamic:
	        #print(feature['properties'])
	        convexs = set()
	        centroid = []

	        for surfaces in feature['geometry']['coordinates']:
	            surface = surfaces[0]
	            surface_z = set(x[2] for x in surface)
	            if len(surface_z) == 1:
	                surface_2d = list((x[0],x[1]) for x in surface)
	            for p in surface:
	                convexs.add(tuple(p))

	        polygon = Polygon(surface_2d)
	        polygon = shapely.geometry.polygon.orient(polygon)
	        polygon_alles.append(polygon)



	adj_poly = np.zeros((len(polygon_alles),len(polygon_alles)))
	for c,c_poly in enumerate(polygon_alles):
	    for a,a_poly in enumerate(polygon_alles):
	        adj_poly[c,a] = c_poly.distance(a_poly)

	pw_dis = list(adj_poly[np.triu_indices(len(polygon_alles))])
	pw = [y for y in pw_dis if y != 0.0]

	min_per = 2
	max_per = 5
	percentile = list(np.arange(min_per,max_per,0.1))
	min_samples_ = [3,4]
	eps_ = []
	para_dist = []

	si_max = -1

	for min_samples in min_samples_:
	    for val in percentile:
	        eps = np.percentile(pw,val)
	        dbscan = cluster.DBSCAN(
	            eps=eps,
	            min_samples=min_samples,
	            metric='precomputed')
	        labels = dbscan.fit_predict(adj_poly)
	        if(len(set(labels)) == 1):
	            SI_score = 'NA'
	        else:
	            SI_score = metrics.silhouette_score(adj_poly,labels,metric="precomputed")
	       
	            para_dist.append({'eps':eps,'min_sample':min_samples,'SI':SI_score})
	            if (SI_score > si_max):
	                si_max = SI_score
	                para_set_max = [val,eps,min_samples]
	        
	newlist = sorted(para_dist, key=lambda k: k['SI'],reverse=True) 
	good_para = newlist[0:1]

	fig = plt.figure(1, dpi=360)
	fig.subplots_adjust(hspace = 0.4,wspace=0.05)
	#ind_plot = [221,222,223,224]#location of subplots
	ind_plot = [111]
	#parameter swap
	for ind,val in enumerate(good_para):
	   
	    ax = fig.add_subplot(ind_plot[ind])
	    eps = val['eps']
	    min_samples = val['min_sample']
	    SI_score = val['SI']
	    dbscan = cluster.DBSCAN(eps=eps,min_samples=min_samples,metric='precomputed')
	    labels = dbscan.fit_predict(adj_poly)
	    
	    core_samples_mask = np.zeros_like(dbscan.labels_, dtype=bool)
	    core_samples_mask[dbscan.core_sample_indices_] = True
	    
	    n_clusters_ = len(set(labels)) #exclusively consider the noisy samples as a cluster
	    
	##plot the colored centroid. same color stands for same clustering
	    unique_labels = set(labels)
	    colors = plt.cm.Spectral(np.linspace(0.1, 1.0, len(unique_labels)))
	    colorcode = {}
	    for k, col in zip(unique_labels, colors):
	        class_member_mask = (labels == k)
	        colorcode[k] = col
	    
	    for i,poly in enumerate(polygon_alles):
	            x,y = poly.exterior.xy
	            ax.plot(x, y, color='#6699cc', alpha=0.7,
	            linewidth=0, solid_capstyle='round', zorder=2)
	        
	## plot polygons 
	    color_space = []
	    for label in labels:
	        color_space.append(colorcode[label])
	            
	    
	    for se,poly in zip(color_space,polygon_alles):
	        patch = PolygonPatch(poly, fc=se, ec =se, alpha=0.7, zorder=1)
	        ax.add_patch(patch)
	        
	    ax.get_xaxis().set_visible(False)
	    ax.get_yaxis().set_visible(False)
	    ax.set_frame_on(False)
	    ax.set_title('SI score: %s\nDetected %s neighborhoods' % (round(SI_score,3),len(unique_labels)) ,size=10)


	img_loc = 'data/luci_test_.png'#can change to your own directory
	fig.savefig(img_loc)
	fig.clear()
	
	return img_loc

