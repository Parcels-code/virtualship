import cartopy.crs as ccrs
import matplotlib.pyplot as plt

REGIONS = {
    "Irminger Sea": {"label": "1", "coords": (57.25, -33.0)},
    "California Current": {"label": "2", "coords": (35, -132)},
    "Gulf Stream and Deep Western Boundary Current": {
        "label": "3",
        "coords": (32.0, -72.0),
    },
    "Japan current": {"label": "4", "coords": (31.7, 141)},
    "Atlantic Meridional Overturning Circulation (AMOC)": {
        "label": "5",
        "coords": (26, -47),
    },
    "El Niño Southern Oscillation (ENSO)": {"label": "6", "coords": (-5.0, -91.5)},
    "North Brazil current": {"label": "7", "coords": (2.0, -43.0)},
    "Somali current": {"label": "8", "coords": (6.0, 53.0)},
    "East Australian Current": {"label": "9", "coords": (-28.0, 156)},
    "Drake passage": {"label": "10", "coords": (-58.0, -57.0)},
    "Agulhas Leakage": {"label": "11", "coords": (-42.0, 15.0)},
    "Bay of Bengal": {"label": "12", "coords": (11.0, 83.0)},
    "Brazil-Malvinas Confluence": {"label": "13", "coords": (-35.0, -48.0)},
    "Cross-shelf exchange on the European North-West Shelf Seas": {
        "label": "14",
        "coords": (48.0, -21.0),
    },
    "European North-West Shelf Seas": {"label": "15", "coords": (54.0, -3.0)},
}


def _global_plot(width=10, height=5, regions=None) -> None:
    fig = plt.figure(figsize=(width, height), dpi=300)
    ax = fig.add_subplot(1, 1, 1, projection=ccrs.Robinson())

    ax.set_global()

    if regions:
        for _, info in regions.items():
            ax.text(
                info["coords"][1],
                info["coords"][0],
                info["label"],
                transform=ccrs.PlateCarree(),
                fontsize=8,
                fontweight="bold",
                color="red",
            )

    ax.stock_img()
    ax.coastlines(linewidth=0.5)
