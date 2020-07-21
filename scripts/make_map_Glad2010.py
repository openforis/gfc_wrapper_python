from utils import parameters as pm
from utils import utils
import os
import gdal
import osr

def make_map_Glad2010(assetID, threshold):
    
    aoi_name = utils.get_aoi_name(assetID)
    
    # skip if process already finished 
    clip_map = pm.getGfcDir() + aoi_name + "_" + str(threshold) + '_map_clip.tif'
    print(clip_map)
    
    if os.path.isfile(clip_map): 
        return 'Glad 2010 map already performed'
    
    # align glad with GFC 
    mask = pm.getDwnDir() + aoi_name + '_' + pm.getTypes()[3] + '.tif'
    
    if not os.path.isfile(mask): 
        return 'No dataframe gfc map'
    
    src = gdal.Open(mask)
    proj = osr.SpatialReference(wkt=src.GetProjection())
    bb = utils.get_bounding_box(assetID)
    res = {}
    _, res['x'], _, _, _, res['y']  = src.GetGeoTransform()
    src = None
    
    # align GFC tree cover with segments 
    glad_raw = pm.getDwnDir() + aoi_name + '_treecover2010.tif'
    glad_aligned = pm.getDwnDir() + aoi_name + '_treecover2010_aligned.tif'
    
    if not os.path.isfile(mask): 
        return 'No treecover file'
    
    options = gdal.WarpOptions(
        xRes             = res['x'], 
        yRes             = res['y'], 
        creationOptions  = "COMPRESS=LZW", 
        outputBounds     = [int(bb[i]) for i in bb],
        #options          = 'overwrite',
        dstSRS           = proj
        
    )
    
    ds = gdal.Warp(glad_aligned, glad_raw, options=options)
    ds = None
    
    # Combination FNF 2000
    treecover_2000 = pm.getDwnDir() + aoi_name + '_' + pm.getTypes()[0] + '.tif'
    fnf_2000 = pm.getTmpDir() + aoi_name + '_fnf2000.tif'
    calc = "(A>={0})*1+(A<{0})*2".format(threshold)
    
    command = [
        'gdal_calc.py',
        '-A', treecover_2000,
        '--co', 'COMPRESS=LZW',
        'outfile='+fnf_2000,
        '--calc="{}"'.format(calc)
    ]
    
    os.system(' '.join(command))
    
    # Combination FNF 2010
    fnf_2010 = pm.getTmpDir() + aoi_name + '_fnf2010.tif'
    command = [
        'gdal_calc.py',
        '-A', glad_aligned,
        '--co', 'COMPRESS=LZW',
        'outfile='+fnf_2010,
        '--calc="{}"'.format(calc)
    ]
    
    os.system(' '.join(command))
    
    #combine into national scale map
    calc = "(A==1)*(B==1)*((C==0)+(C>=11))*1+"   # Foret accord
    calc += "(A==1)*(B==1)*( C> 0)*(C < 11)*2+"  # Pertes GLAD < Pertes GFC
    calc += "(A==1)*(B==2)*( C> 0)*(C < 11)*3+"  # Pertes accord
    calc += "(A==1)*(B==2)*((C==0)+(C>=11))*4+"  # Pertes GLAD > Pertes GFC
    calc += "(A==2)*(B==1)*( D==1)*5+"           # Gains accord
    calc += "(A==2)*(B==1)*( D==0)*6+"           # Gains GLAD > Gains GFC
    calc += "(A==2)*(B==2)*( D==1)*7+"           # Gains GLAD < Gains GFC
    calc += "(A==2)*(B==2)*( D==0)*8"            # Non Foret accord
    
    glad_loss = pm.getDwnDir() + aoi_name + '_' + pm.getTypes()[1] + '.tif'
    glad_gain = pm.getDwnDir() + aoi_name + '_' + pm.getTypes()[2] + '.tif'
    glad_check = pm.getTmpDir() + aoi_name + '_glad_check.tif'
    
    command = [
        'gdal_calc.py',
        '-A', fnf_2000,
        '-B', fnf_2010,
        '-C', glad_loss,
        '-D', glad_gain,
        '--co', 'COMPRESS=LZW',
        '--overwrite',
        '--outfile={}'.format(glad_check),
        '--calc="{}"'.format(calc)
    ]
    
    os.system(' '.join(command))   
    
    
    #crop to country boundaries and reproject in EA projections 
    
    glad_prj = pm.getTmpDir() + aoi_name + 'glad_check.tif'

    options = gdal.WarpOptions(
        dstSRS = proj,
        outputType = gdalconst.GDT_Byte,
        creationOptions = "COMPRESS=LZW", 
        cutlineDSName = aoi_shp
    )
    
    ds = gdal.Warp(glad_prj, glad_check, options=options)
    ds = None
    
    # add pseudocolor table to results 
    glad_pct = pm.getTmpDir() + aoi_name + '_glad_check_pct.tif'
    command = [
        "(echo {})".format(pm.getUtilsDir()+'color_table_glad.txt'),
        '|',
        'oft-addpct.py',
        glad_check,
        glad_pct
    ]
     
    os.system(' '.join(command))
     
    # compress     
    options = gdal.TranslateOptions(
        outputType = gdalconst.GDT_Byte,
        creationOptions = "COMPRESS=LZW",
    )
    
    gdal.translate(clip_map, glad_pct, options)
    
    
    return 1