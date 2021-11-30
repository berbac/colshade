'''
Erzeugt ein koloriertes und schattiertes Relief im Tiff-Format.
'''
import glob
import gdal
import numpy as np


# Variablen
workDir = 'C:\\Users\\Admin\\GIS_Projekte\\'  # hier wird alles abgelegt
inDirectory = 'C:\\Users\\Admin\\GIS_Projekte\\Schwarzwald\\'  # hier sind die Tifs
fileExt = 'tif'                     # Dateierweiterung der Eingangsdateien
outName = 'schwarzwald.tif'         # Name der Ausgabedatei
colRampFile = 'schwarzwald.txt'     # diese Datei enthält die Farbpallete
stepCount = 1


# ++ Funktionen ++ 

def collectfiles(directory, ext):
    '''
    Sammelt alle Dateien mit Erweiterung 'ext' in einem Verzeichnis 'dir' und
    gibt ein Array aus.
    '''

    fList = glob.glob(directory + "*." + ext)
    if len(fList) > 0:
        print("Es wurden %s zu verarbeitende Dateien gefunden:"
              % len(fList))

        for file in fList:
            print(file)
            
        return fList
    else:
        print("Ordner", workDir, "enthält keine Dateien des Typs", ext,
              "\nProgramm wird beendet.")
        quit()


def hsProcess(inFile, outFile, azimuth, angle_altitude, z_factor=0.00001):
    '''
    Funktioniert nur bei kleinen Projekten (speicherintensiv.)
    Gibt einen Hillshade als Tif File aus, welche aus Höhendaten
    eines DEM-Tiffs errechnet wird.
    Folgt der Formel:
    Hillshade = 255.0 * ((cos(zenith_I) * cos(slope_T)) +
                (sin(zenith_I) * sin(slope_T) * cos(azimuth_I-aspect_T))
    siehe: https://desktop.arcgis.com/en/arcmap/10.3/tools/spatial-analyst-toolbox/how-hillshade-works.htm
    '''

    ds = gdal.Open(inFile)
    band = ds.GetRasterBand(1)
    arr = band.ReadAsArray()
    [cols, rows] = arr.shape

    # ab hier Hillshadeberechnung
    azimuth = (360.0 - azimuth)
    x, y = np.gradient(arr)
    slope = np.pi / 2. - np.arctan(np.sqrt(x * x + y * y))
    aspect = np.arctan2(-x, y)
    azimuthrad = azimuth * np.pi / 180.
    altituderad = (angle_altitude * np.pi / 180.)
    shade = 255 * (np.sin(altituderad) * np.sin(slope)
                   + np.cos(altituderad) * np.cos(slope)
                   * np.cos((azimuthrad - np.pi / 2.) - aspect) + 1) / 2

    # Tiff-File schreiben
    driver = gdal.GetDriverByName("GTiff")
    outdata = driver.Create(outFile, rows, cols, 1, gdal.GDT_UInt16)
    outdata.SetGeoTransform(ds.GetGeoTransform())  # Geotransformation aus Input
    outdata.SetProjection(ds.GetProjection())      # Projektion aus Input
    outdata.GetRasterBand(1).WriteArray(shade)
    outdata.FlushCache()  # erst hier wird die Datei geschrieben


def combinetiff(relief, hs, output):
    '''
    Diese Funktion kombiniert die beiden gegebenen Tiffs so, dass
    Hillshade und farbkodierte Höhendaten gemeinsam zu sehen sind.
    Dazu werden die einzelnen Pixelwerte des Hillshades genutzt, um
    die entsprechenden Werte aller drei Bänder der Höhendaten zu verdunkeln,
    was eine Struktur entstehen lässt.
    '''

    hsDs = gdal.Open(hs)
    rel = gdal.Open(relief)
    gray = hsDs.GetRasterBand(1).ReadAsArray()
    [cols, rows] = gray.shape
    band1 = np.array(rel.GetRasterBand(1).ReadAsArray())
    band2 = np.array(rel.GetRasterBand(2).ReadAsArray())
    band3 = np.array(rel.GetRasterBand(3).ReadAsArray())
    driver = gdal.GetDriverByName("GTiff")
    result = driver.Create(output, rows, cols, 3, gdal.GDT_UInt16)
    result.SetGeoTransform(hsDs.GetGeoTransform())  # Geotransformation aus Input
    result.SetProjection(hsDs.GetProjection())      # Projektion aus Input
    result.GetRasterBand(1).WriteArray((gray / 255) * band1)
    result.GetRasterBand(2).WriteArray((gray / 255) * band2)
    result.GetRasterBand(3).WriteArray((gray / 255) * band3)
    result.FlushCache()  # erst hier wird die Datei geschrieben



# ++ Sequenzen ++ : Anweisungen und Subroutinen, die nacheinander aufgerufen werden

gdal.UseExceptions()  # GDAL gibt Exceptions statt ERRORS aus

print("Schritt %s: Rasterdaten sammeln"
      % stepCount)
stepCount += 1
allFiles = collectfiles(inDirectory, fileExt)

print("\nSchritt %s: Mosaikieren"
      % stepCount)
stepCount += 1
mergeOptions = gdal.WarpOptions(format='GTiff',
                                dstNodata=None)
try:
    gdal.Warp(workDir + 'merged.tif', allFiles, options=mergeOptions)
except RuntimeError:
    print("Fehler: Dateiformat nicht untersützt! (.%s) \
          \nProgramm wird beendet"
          % fileExt)
    quit()
print("fertig")

print("\nSchritt %s: Rasterdaten in Dataset für GDAL umwandeln..."
      % stepCount)
stepCount += 1
rasterDataset = gdal.Open(workDir + 'merged.tif', gdal.GA_ReadOnly)
print("fertig")

print("\nSchritt %s: Hillshade generieren..."
      % stepCount)
stepCount += 1
hsOptions = gdal.DEMProcessingOptions(format='GTiff',
                                      zFactor=0.00001,  # Umrechnungsfaktor von Meter zu Grad (Näherung)
                                      scale=1,
                                      azimuth=315,
                                      altitude=45)
gdal.DEMProcessing(workDir + 'hillshade.tif',
                   rasterDataset,
                   processing='hillshade',
                   options=hsOptions)
rasterDataset = None  # um Speicher zu schonen wird das Dataset gelöscht
print("fertig")

# alternative Berechnung über die oben gegebene Funktion (langsamer/unschöner):
# print("\nBerechnen des alternativen Hillshades hillshade2.tif...")
# hsProcess(workDir + 'merged.tif', workDir + 'hillshade2.tif', 315, 45)
# print("fertig")

print("\nSchritt %s: Kolorierung der Höhendaten..."
      % stepCount)
stepCount += 1
colOptions = gdal.DEMProcessingOptions(format='GTiff',
                                       colorFilename=(workDir + colRampFile),
                                       addAlpha=False)
gdal.DEMProcessing(workDir + 'col_relief.tif',
                   workDir + 'merged.tif',
                   processing='color-relief',
                   options=colOptions)
print("fertig")

print("\nSchritt %s: Kombinieren der Dateien..."
      % stepCount)
stepCount += 1
combinetiff(workDir + 'col_relief.tif',
            workDir + 'hillshade.tif',
            workDir + outName)
print("fertig")

print("\n\t**Prozess beendet**")
print("\nErgebnisse\nMosaikierung:\n\t", workDir + "merged.tif",
      "\nHillshade:\n\t", workDir + "hillshade.tif",
      "\nKolorierte Höhendaten:\n\t", workDir + "col_relief.tif",
      "\nGesamtresultat:\n\t", workDir + outName)

