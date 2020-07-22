from utils import parameters as pm
from utils import utils
import os
import gdal
import osr
from osgeo import gdalconst


def make_map_threshold_clump(assetId, threshold):
    
    aoi_name = utils.get_aoi_name(assetId)
    aoi_shp = pm.getDwnDir() + '{}.shp'.format(aoi_name)
    
    #skip if outpu already exist 
    clip_map_clump = pm.getGfcDir() + aoi_name + '_{}_gfc_clump_map.tif'.format(threshold)
    
    if os.path.isfile(clip_map_clump):
        return 'gfc clump map already performed'
    
    
    # align glad with GFC 
    mask = pm.getDwnDir() + aoi_name + '_' + pm.getTypes()[3] + '.tif'
    
    if not os.path.isfile(mask): 
        return 'No dataframe gfc map'
    
    src = gdal.Open(mask)
    proj = osr.SpatialReference(wkt=src.GetProjection())
    bb = utils.get_bounding_box(assetId)
    res = {}
    _, res['x'], _, _, _, res['y']  = src.GetGeoTransform()
    src = None
    
    #combination into national scale map 
    "treecover2000","lossyear","gain","datamask"
    gfc_treecover = pm.getDwnDir() + aoi_name + '_' + pm.getTypes()[0] + '.tif'
    gfc_loss = pm.getDwnDir() + aoi_name + '_' + pm.getTypes()[1] + '.tif'
    gfc_gain = pm.getDwnDir() + aoi_name + '_' + pm.getTypes()[2] + '.tif'
    gfc_datamask = pm.getDwnDir() + aoi_name + '_' + pm.getTypes()[3] + '.tif'
    gfc_tmp_map_clump = pm.getTmpDir() + aoi_name + '_{}_gfc_clump_map.tif'.format(threshold)
    
    calc = "(A<={})*((C==1)*50 + (C==0)*30 +".format(threshold) #Non forest 
    calc += "(A>{})*((C==1)*(".format(threshold)
    calc += "(B>0)*51 +"                                        #gain + loss 
    calc += "(B==0)*50"                                         #gain 
    calc += ") + (C==0) * ("
    calc += "(B>0)*B +"                                         #loss
    calc += "(B==0)*40"                                         #stable forest 
    calc +="))"

    command =[
        'gdal_calc.py',
        '-A', gfc_treecover,
        '-B', gfc_loss,
        '-C', gfc_gain,
        '-D', gfc_datamask,
        '--co="{}"'.format('COMPRESS=LZW'),
        '--outfile={}'.format(gfc_tmp_map_clump),
        '--calc="{}"'.format(calc)
    ]
    
    os.system(' '.join(command))
    
    #crop and reproject
    gfc_map_clump_clip = pm.getTmpDir() + aoi_name + '_{}_gfc_clump_map_clip.tif'.format(threshold)

    options = gdal.WarpOptions(
        dstSRS = proj,
        outputType = gdalconst.GDT_Byte,
        creationOptions = "COMPRESS=LZW", 
        cutlineDSName = aoi_shp,
        cropToCutline   = True
    )
    
    ds = gdal.Warp(gfc_map_clump_clip, gfc_tmp_map_clump, options=options)
    ds = None
    
    #add pseudo colors 
    color_table = pm.getColorTable()
    gfc_map_clump_clip_pct = pm.getTmpDir() + aoi_name + '_{}_gfc_clump_map_clip_pct.tif'.format(threshold)
    command = [
        "(echo {})".format(color_table),
        '|',
        'oft-addpct.py',
        gfc_map_clump_clip,
        gfc_map_clump_clip_pct
    ]
     
    os.system(' '.join(command))
    
    #compress 
    options = gdal.TranslateOptions(
        outputType = gdalconst.GDT_Byte,
        creationOptions = "COMPRESS=LZW",
    )
    
    gdal.Translate(clip_map_clump, gfc_map_clump_clip_pct, options=options)
    
    return 1




