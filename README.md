# EVI-OnDemand

EVI-OnDemand is a simulation platform which estimates fast-charging infrastructure requirements necessary to support ride-hailing electrification. The tool belongs to the broader EVI-X family, a consortium of [infrastructure modeling tools](https://www.nrel.gov/transportation/data-tools.html#vehicles) created by researchers at the National Renewable Energy Laboratory.

### Setup Instructions

First, clone the repository from GitHub:

```
git clone https://github.com/NREL/EVI-OnDemand.git
```

EVI-OnDemand is written in Python and requires two packages to run: pandas and yaml. A third package, tqdm is also used to support command-line reporting. Note that this setup requires Anaconda, which can be obtained [here](https://docs.anaconda.com/anaconda/install/index.html).

````
conda create -n evi-ondemand python=3.7
conda activate evi-ondemand
conda install pandas
pip install pyyaml
pip install tqdm
````

### Simulation Execution
To execute EVI-Ondemand, first navigate to the scenarios/ folder within the EVI-OnDemand repository:
```
cd scenarios
```


Next, call the model and clarify which scenario to run through the following command:

```
python ../src/ondemand_fleetsim.py bau_baseline.yaml
```

This will execute the model and outputs will be written to the outputs/ folder. The aggregated nature of EVI-OnDemand enables rapid simulation times; on average, runs finish in less than 30 seconds.

```
Beginning simulation...

CBSA 383: 100%|██████████████████████████████████████████████████████████████████████| 384/384 [00:08<00:00, 47.39it/s]


Simulation finished!
Number of plugs: 25466
Number of vehicles: 1454009
Plugs per 1000 vehs: 17.51
```

Additional simulations can be performed by creating additional input .yaml files with varying input parameters. Any questions pertaining to the model should be directed to Matthew Moniot at matthew.moniot@nrel.gov
