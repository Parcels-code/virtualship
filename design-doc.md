# VirtualShip Design Document

> Document created as a result of [this discussion topic](https://github.com/OceanParcels/virtualship/discussions/187).

## Essence of VirtualShip

VirtualShip interpolates hydrodynamical and biogeographical fields the way instruments would. **Student Users** can combine these observations into an expedition (also known as a "cruise"). **Research Users** can also deploy individual instruments in these field, either as part of an expedition or independently, to compare against actual observations.

### For Researchers

- Define or configure instruments to make **deployments** of virtual instruments in the flow field (passed to parcels).

### For Students or Researchers Planning an Expedition

A layer on top allows them to:

- Run an **expedition** that chains together **deployments** at different **stations**.

---

## Key Concepts

### Measurement

- A spacetime interpolation of a hydrodynamic or biogeochemical field.
- A set of measurements forms a timeseries output (serialised to disk as a zarr output).
  - In the case of students, this could be serialized with artificial errors to simulate real-world data and also be serialized in the original (binary or csv) format of the instrument.

### Instrument

- A device that takes measurements. Two types:
  - **Underway-instruments**: Measure continuously during the expedition (e.g., Thermosalinograph, shipboard ADCP, and (to be developed) meteorology).
    - Conducted for the entirety of the expedition and continues recording when ship is stationary at a **station**.
  - **Overboard-instruments**: Deployed at specific times (e.g., CTD, drifters, Argo, XBT).
    - Deployed at stations during the expedition.
- Components:
  - A Parcels fieldset (which relates to a Copernicus Marine dataset)
  - A Parcels kernel
  - (optional) A configuration object controlling any important parameters.

### Deployment

- A complete set of measurements for an overboard-instrument (from deployment to retrieval or end-of-life).
- Each deployment is executed independently of the ship's movement.
- Components:
  - An instrument.
  - A station.
  - A start time.

### Ship Track

- A set of line segments between stations where underway-instruments take measurements.
  - **Planned ship track**: Includes arrival and departure times at stations.
  - **Realised ship track**: Actual path taken.

### Waypoint

- A horizontal location with no associated time.
  - **Planned waypoint** - has no associated time
  - **Realised waypoint** - has an associated time (since the timing has been calculated from the ship speed).

### Station

- A waypoint where multiple deployments can occur. The ship does not drift horizontally while at a station.
- Features:
  - One waypoint.
  - An associated time for deployment start.
- Ships travel between stations at maximum speed; if arriving early, they wait at the station.

### Port

- A waypoint where a ship track starts or ends, but no deployments are possible.

---

pseudocode

```
for each station
 for each overboard-instrument
 do deployment
 while track to next station
  for each underway-instrument
   do measurement
```

---

### Problems

Simulated problems that are encountered during an expedition.

# Technical Decisions

## Running the expedition

Two possible approaches:

1. Run a planning phase and deploy instruments after

- Steps:
  - The planned ship track is known, verified[^1], and then iterated through (encountering problems along the way).
  - Users adjust their plans based on the problems encountered.
  - Once completed, the ship track is finalised (i.e., is _realized_) and then all the deployments are made and measurements are taken.
- Pros:
  - Easier to implement and test (distinct phases in the running of the code).
  - Instruments can be run in non-chronological order (i.e., as different particlesets with different fieldsets) - simplifying code and output.
- Cons:
  - Problems become limited (can only make problems based on the planned ship track. Not possible to encounter problems based on the conditions of the Parcels simulation (e.g., currents)).
  - Students cannot make decisions based on the data they have "collected" up to the point that they have to make a decision[^2] .

2. Encounter problems during the expedition

- Steps:
  - The planned ship track is known, verified[^1], and then the expedition is run.
  - Expedition is paused when a problem is encountered, and users can adjust their plans.
- Pros:
  - Problems can be flexible and based on the Parcels simulation (e.g., currents).
- Cons:
  - More complex to implement and test (need to run the code in a single phase).
  - Everything is a single particleset and fieldset, making kernels more complex, requiring splitting of the outputs into separate zarr files.
  - Students can't make decisions based on the data they have "collected".

We have decided for approach (1) for the timebeing. Down the line we may want to explore approach (2).

## Configuration Files

- **ship_config.yaml** and **schedule.yaml** can be updated to match the current structure.
- These can be consolidated into a single **expedition.yaml** file.

# FAQ

- How does this "Essence of VirtualShip" above fit for biological oceanography? Do they also have a concept of 'instruments'?
  - For now let's focus on field data that is provided through the Copernicus Marine Service (down the line we might support other data providers).

---

[^1]: Verify -> Make sure that ship track isn't on land, make sure that the ship track isn't unrealistic for the ship speed.

[^2]: If we want to support this, there will be added complexity: we will need to show the users the binary files, but the zarr files behind the scenes will still need to be cached so that the simulation can continue from where it left off.
