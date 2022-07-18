from matplotlib import pyplot as plt
from matplotlib.widgets import Slider
from matplotlib.dates import DateFormatter
import csv
import numpy
import argparse
from datetime import datetime, timedelta


parser = argparse.ArgumentParser(description="python tool to plot csv recordings from omblepy")
parser.add_argument("-w", "--windowsize", type=int, default="7", help="size of the viewing plot x axis window")
parser.add_argument("-b", "--binsize", type=int, default="1", help="number of days over which the measurements are combined and averaged")
parser.add_argument("inputfile", type=str, help="path to the input csv file")
args = parser.parse_args()

daysInOneBin = args.binsize
dateWindowLengthInDays = args.windowsize
inputpath = args.inputfile.strip("'").strip('\"')

date1 = []
dia1 = []
sys1 = []
with open(inputpath, mode='r', newline='', encoding='utf-8') as infile:
    reader = csv.DictReader(infile)
    for record in reader:
        date1.append(datetime.fromisoformat(record["datetime"]))
        sys1.append(float(record["sys"]))
        dia1.append(float(record["dia"]))


def gradient_image(ax, extent, direction=0.3, cmap_range=(0, 1), **kwargs):
    #from https://matplotlib.org/stable/gallery/lines_bars_and_markers/gradient_bar.html
    v = numpy.array([1, 0])
    X = numpy.array([[v @ [1, 0], v @ [1, 1]],
                  [v @ [0, 0], v @ [0, 1]]])
    a, b = cmap_range
    X = a + (b - a) / X.max() * X
    im = ax.imshow(X, extent=extent, interpolation='bicubic',
                   vmin=0, vmax=1,aspect='auto', **kwargs)
    return im

def averageValuesInBins(dates, dia, sys, timedelta = timedelta(days = 1)):
    dateDecimated = []
    diaDecimated = []
    sysDecimated = []
    lastDate = datetime(1990, 1, 1).date()
    for dateIdx, date in enumerate(date1):
        if(lastDate <= date.date() and date.date() <= lastDate + timedelta):
            numSameDates += 1
            sysDecimated[-1] += sys1[dateIdx]
            diaDecimated[-1] += dia1[dateIdx]
        else:
            if(dateIdx != 0):
                sysDecimated[-1] /= numSameDates #average
                diaDecimated[-1] /= numSameDates #average
            numSameDates = 1
            dateDecimated.append(date.date())
            sysDecimated.append(sys1[dateIdx])
            diaDecimated.append(dia1[dateIdx])
            lastDate = date.date()
        if(dateIdx == len(date1) - 1):
            sysDecimated[-1] /= numSameDates #average
            diaDecimated[-1] /= numSameDates #average
    return dateDecimated, diaDecimated, sysDecimated


dateDecimated, diaDecimated, sysDecimated = averageValuesInBins(date1, dia1, sys1, timedelta(days = daysInOneBin))

heighDecimated = []
for idx in range(len(diaDecimated)):
    heighDecimated.append(sysDecimated[idx] - diaDecimated[idx])

def colorPressureRangeBackground(ax, yMin, yMax, alpha):
    yLim = plt.gca().get_ylim()
    extYmin = (yMin - yLim[0]) / (yLim[1] - yLim[0])
    extYmax = (yMax - yLim[0]) / (yLim[1] - yLim[0])
    gradient_image(ax, extent=(0, 1, extYmin, extYmax), transform=ax.transAxes, cmap=plt.cm.hsv, cmap_range=(0.35, 0.0), alpha = alpha)
    
fig, dataAxes = plt.subplots()
plt.ylim(60, 180) #needs to be done before colorPressureRangeBackground is run, so that the function knows the graph dimension in y axis
colorPressureRangeBackground(dataAxes, 70, 110, 0.2)
colorPressureRangeBackground(dataAxes, 120, 160, 0.2)
plt.bar(dateDecimated, bottom=diaDecimated, height=heighDecimated, width=daysInOneBin-0.5, color="blue")
plt.xlim([min(dateDecimated) - timedelta(days = daysInOneBin), max(dateDecimated) + timedelta(days = daysInOneBin)])
plt.xticks(rotation = 90)
date_form = DateFormatter("%d.%m.%y")
dataAxes.xaxis.set_major_formatter(date_form)
plt.xlabel("time")
plt.ylabel("blood pressure [mmHg]")


#time offset slider
sliderMaxValue = ((max(dateDecimated) - min(dateDecimated)).days - (dateWindowLengthInDays - 1))
plt.subplots_adjust(bottom = 0.3)
if(sliderMaxValue > 0):
    lastVal = 0
    def update(val):
        global dataAxes
        global dateDecimated
        global lastVal
        if(abs(lastVal//1 - val//1)<1):
            return #speed up, return when no update is neccesary, since matplotlib x axis granularity is only days
        lastVal = val
        #add pading left and right of daysInOneBin
        newXmin = min(dateDecimated) - timedelta(days = daysInOneBin) + timedelta(days = val) 
        newXmax = min(dateDecimated) + timedelta(days = dateWindowLengthInDays + daysInOneBin - 1) + timedelta(days = val)
        dataAxes.set_xlim([newXmin, newXmax])
    axTimeOffset = plt.axes([0.3, 0.0, 0.60, 0.1])
    print(max(dateDecimated))
    print(min(dateDecimated))

    timeOffset_slider = Slider(
        ax=axTimeOffset,
        label="scroll x-axis [days]",
        valmin=0,
        valmax=sliderMaxValue,
        valinit=sliderMaxValue,
        orientation="horizontal"
    )
    timeOffset_slider.on_changed(update)
    update(sliderMaxValue)


plt.show()