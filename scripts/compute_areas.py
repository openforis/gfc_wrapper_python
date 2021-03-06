import os
from pathlib import Path
import subprocess

from pyproj import CRS
import pandas as pd
from osgeo import osr, gdal
import ee
from bqplot import *
from bqplot import pyplot as plt
import ipyvuetify as v
from matplotlib.colors import to_rgba
from matplotlib import pyplot as plt

from utils import parameters as pm
from utils import utils
from utils import parameters as pm

ee.Initialize()

def create_hist(map_raster, output):
    
    if not os.path.isfile(map_raster): 
        output.add_live_msg('No gfc map', 'error')
        return None
    
    #project raster in world mollweide
    map_raster_proj = f'{pm.getGfcDir()}{Path(map_raster).stem}_proj.tif'
    input_ = gdal.Open(map_raster)
    gdal.Warp(map_raster_proj, input_, dstSRS='ESRI:54009')
    
    #realize a primary hist
    hist = utils.pixelCount(map_raster_proj)
    
    src = gdal.Open(map_raster_proj)
    gt =src.GetGeoTransform()
    resx = gt[1]
    resy =gt[5]
    #src.close()
    
    #convert to hectars
    hist['area'] = utils.toHectar(hist['pixels'], abs(resx), abs(resy))
    
    return hist

def create_hist_ee(ee_map, aoi_io, output): 
    
    #construct the labels
    label = pm.getMyLabel()
    
    columns=['code', 'area_square_meters']
    row_list = []
    geom = aoi_io.get_aoi_ee().geometry()
    for index, code in enumerate(pm.getCodes()):
        output.add_live_msg(f'computing {label[index]}')
        code = int(code)
        mask = ee_map.eq(code)
        mask_surface = mask.multiply(ee.Image.pixelArea())
        stats = mask_surface.reduceRegion(**{
            'reducer': ee.Reducer.sum(),
            'geometry': geom,
            'maxPixels': 1e13
        });
        row_list.append([code, stats.getInfo()['gfc']])

    
    hist = pd.DataFrame(row_list, columns=columns)
    
    #create an hectares column
    hist['area'] = hist['area_square_meters']/10000
    
    #add the labels
    hist['class'] = label
    
    return hist

def plotLoss(df, aoi_name):
    
    d_hist = df[(df['code'] > 0) & (df['code'] < 30)]

    x_sc = LinearScale()
    y_sc = LinearScale()  
    
    ax_x = Axis(label = 'year', scale = x_sc)
    ax_y = Axis(label = 'tree cover loss surface (ha)', scale = y_sc, orientation = 'vertical') 
    bar = Bars(x = [i + 2000 for i in d_hist['code']], y = d_hist['area'], scales = {'x': x_sc, 'y': y_sc})
    title = f'Distribution of tree cover loss per year in {aoi_name}'
    fig = Figure(
        title     = title,
        marks     = [bar], 
        axes      = [ax_x, ax_y], 
        padding_x = 0.025, 
        padding_y = 0.025
    )
    
    return fig

def areaTable(df):
    #construct the total loss line
    df_loss = df[(df['code'] > 0 ) & (df['code'] < 30)] 
    df_loss = df_loss.sum()
    df_loss['code'] = 60
    df_loss['class'] = 'loss'
    df_masked = df.append(df_loss, ignore_index=True)
    
    #drop the loss_[year] lines
    df_masked = df_masked[df_masked['code'] >= 30] 
    
    #create the header
    headers = [
        {'text': 'Class', 'align': 'start', 'value': 'class'},
        {'text': 'Area (ha)', 'value': 'area' }
    ]
    
    items = [
        {'class':row['class'], 'area':f'{int(row.area)}'} for index, row in df_masked.iterrows()
    ]
    
    table = v.DataTable(
        class_             = 'ma-3',
        headers            = headers,
        items              = items,
        disable_filtering  = True,
        disable_sort       = True,
        hide_default_footer= True
    )
    
    return table
    
def compute_ee_map(aoi_io, threshold):
     
    #load the dataset and AOI
    dataset = ee.Image(pm.getDataset())
    aoi = aoi_io.get_aoi_ee()

    #clip the dataset on the aoi 
    clip_dataset = dataset.clip(aoi)
        
    #create a composite band based on the user threshold 

    calc = "gfc = (A<={0})*((C==1)*50 + (C==0)*30) + " #Non forest 
    calc += "(A>{0})*(C==1)*(B>0)*51 + "         #gain + loss 
    calc += "(A>{0})*(C==1)*(B==0)*50 + "        #gain                                             
    calc += "(A>{0})*(C==0)*(B>0)*B + "          #loss
    calc += "(A>{0})*(C==0)*(B==0)*40"           #stable forest

    calc = calc.format(threshold)
    
    bands = {
        'A': clip_dataset.select('treecover2000'),
        'B': clip_dataset.select('lossyear').unmask(0), #be carefull the 0 values are now masked
        'C': clip_dataset.select('gain'),
    }
    
    gfc = clip_dataset.expression(calc,bands)
    
    return gfc.select('gfc').uint8()

def export_legend(filename):
    
    #create a color list
    color_map = []
    for index in pm.get_gfc_colors(): 
        color_map.append([val for val in list(pm.get_gfc_colors()[index])])

    columns = ['entry']
    rows = [' '*10 for index in pm.get_gfc_colors()] #trick to see the first column
    cell_text = [[index] for index in pm.get_gfc_colors()]

    fig, ax = plt.subplots(1,1, figsize=[6.4, 8.6])

    #remove the graph box
    ax.axis('tight')
    ax.axis('off')

    #set the tab title
    ax.set_title('Raster legend')

    #create the table
    the_table = ax.table(
        colColours = [to_rgba('lightgrey')],
        cellText   = cell_text,
        rowLabels  = rows,
        colWidths  = [.4],
        rowColours = color_map,
        colLabels  = columns,
        loc        = 'center'
    )
    the_table.scale(1, 1.5)

    #save &close
    plt.savefig(filename)
    plt.close()
    
    return