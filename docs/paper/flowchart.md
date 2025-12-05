```{mermaid}
---
config:
  theme: default
  layout: elk
  look: handDrawn
---
flowchart TB

 subgraph s3["v0.3"]
        n22["Copernicus Marine Data Store"]
        n23["zarr"]
        n28["copernicusmarine toolbox"]
        n29["Marine data"]
        n31["xarray"]
        n33["<b>VirtualShip (v0.3 / v1)</b>"]
        n34["Instrument classes"]
        n35["<b>Parcels</b>"]
        n36["Output data"]
        n57["VirtualShip Classroom"]
  end

    n22 --- n23
    n28 --> n29
    n23 --- n31
    n31 --> n28
    n33 --> n34
    n34 --> n35
    n35 --> n36
    n29 --> n33
    n57 --- n33

    n22@{ shape: db}
    n23@{ shape: text}
    n28@{ shape: rect}
    n29@{ shape: out-in}
    n31@{ shape: text}
    n33@{ shape: rect}
    n34@{ shape: rect}
    n35@{ shape: rect}
    n36@{ shape: in-out}
    n57@{ shape: text}
    style n22 fill:#BBDEFB
    style n28 fill:#C8E6C9
    style n29 fill:#FFCDD2
    style n33 fill:#C8E6C9
    style n34 fill:#FFF9C4
    style n35 fill:#C8E6C9
    style n36 fill:#E1BEE7
    style n57 fill:transparent
```

**Notes:**

- Toggle subgraphs using the script variables (generate_mermaid.py).
- Parcels v4, ARCO-ready interpolator with behaviour customisability.
- Phase 1 is also a 'proof of concept' for combining multiple streams of (ARCO) data to VirtualShip platform.
- Phase 2 would expand VirtualShip (and therefore Parcels) beyond oceanography, in line with the recent Parcels re-brand.
- ECMWF are working on ARCO-ready data lake for C3S and CAMS as we speak... https://climate.copernicus.eu/work-progress-our-data-stores-turn-arco
- Atmospheric data can also include CAMS, i.e. air quality, pollution etc.
