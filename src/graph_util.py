"""Source: https://stackoverflow.com/questions/7908636/how-to-add-hovering-annotations-to-a-plot"""


from matplotlib.collections import PathCollection
from matplotlib.figure import Figure
from matplotlib.pyplot import Axes
from matplotlib.text import Annotation


def add_hover_annotations(scatter: PathCollection, axes: Axes, figure: Figure, names: list):
    annotation = axes.annotate(
        "",
        xy=(0, 0),
        xytext=(20, 20),
        textcoords="offset points",
        bbox=dict(boxstyle="round", fc="w"),
        arrowprops=dict(arrowstyle="->"),
    )
    annotation.set_visible(False)
    figure.canvas.mpl_connect(
        "motion_notify_event", lambda event: hover(event, scatter, axes, figure, names, annotation)
    )


def update_annot(scatter: PathCollection, ind, names: list, annotation: Annotation):
    pos = scatter.get_offsets()[ind["ind"][0]]
    annotation.xy = pos
    text = " ".join([names[n] for n in ind["ind"]])
    annotation.set_text(text)
    annotation.get_bbox_patch().set_alpha(0.4)


def hover(event, scatter: PathCollection, axes: Axes, figure: Figure, names: list[str], annotation: Annotation):
    vis = annotation.get_visible()
    if event.inaxes == axes:
        cont, ind = scatter.contains(event)
        if cont:
            update_annot(scatter, ind, names, annotation)
            annotation.set_visible(True)
            figure.canvas.draw_idle()
        else:
            if vis:
                annotation.set_visible(False)
                figure.canvas.draw_idle()
