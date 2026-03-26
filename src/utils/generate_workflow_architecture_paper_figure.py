#!/usr/bin/env python3
"""Generate a paper-focused workflow architecture figure."""

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch


def box(ax, x, y, w, h, title, subtitle="", fc="#f8fafc", ec="#334155", lw=1.4):
    p = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.01,rounding_size=0.015",
        linewidth=lw,
        edgecolor=ec,
        facecolor=fc,
    )
    ax.add_patch(p)
    ax.text(x + w/2, y + h*0.62, title, ha="center", va="center", fontsize=10.5, weight="bold", color="#0f172a")
    if subtitle:
        ax.text(x + w/2, y + h*0.28, subtitle, ha="center", va="center", fontsize=8.6, color="#475569")


def arrow(ax, a, b, color="#334155", lw=1.6, style="-|>", rad=0.0, linestyle="solid"):
    arr = FancyArrowPatch(
        posA=a,
        posB=b,
        arrowstyle=style,
        mutation_scale=10,
        linewidth=lw,
        color=color,
        linestyle=linestyle,
        connectionstyle=f"arc3,rad={rad}",
    )
    ax.add_patch(arr)


def main(path="workflow_architecture_paper.png"):
    fig, ax = plt.subplots(figsize=(13, 5.2), dpi=220)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(0.03, 0.95, "Multi-Node Workflow Orchestration", fontsize=16, weight="bold", color="#0f172a", ha="left", va="top")

    y = 0.47
    w = 0.105
    h = 0.18
    gap = 0.028
    x0 = 0.04

    xs = [x0 + i * (w + gap) for i in range(7)]
    nodes = [
        ("Architect", "planning + routing"),
        ("Reviewer", "validation gate"),
        ("Input Writer", "load-modify-write"),
        ("Runner", "execution"),
        ("Analysis", "metrics + checks"),
        ("Reviewer", "post-run checks"),
        ("Visualization", "slices + profiles"),
    ]

    for x, (title, subtitle) in zip(xs, nodes):
        box(ax, x, y, w, h, title, subtitle)

    # Main chain arrows
    for i in range(len(xs) - 1):
        arrow(ax, (xs[i] + w, y + h/2), (xs[i+1], y + h/2))

    # Requested direct edge: Architect -> Input Writer
    arrow(
        ax,
        (xs[0] + w/2, y + h),
        (xs[2] + w/2, y + h),
        color="#0f766e",
        lw=1.7,
        rad=0.0,
        linestyle="dashed",
    )
    ax.text((xs[0] + xs[2] + w)/2, y + h + 0.045, "direct plan handoff", ha="center", va="bottom", fontsize=8.5, color="#0f766e")

    # Planning/refinement loop
    arrow(
        ax,
        (xs[1] + w/2, y),
        (xs[0] + w/2, y),
        color="#7c3aed",
        lw=1.4,
        rad=0.0,
        linestyle="dashed",
    )
    ax.text((xs[0] + xs[1] + w)/2, y - 0.05, "replan on failed review", ha="center", va="top", fontsize=8.2, color="#7c3aed")

    # Section guides
    ax.plot([xs[0], xs[1] + w], [0.30, 0.30], color="#94a3b8", lw=1.2)
    ax.plot([xs[2], xs[4] + w], [0.30, 0.30], color="#94a3b8", lw=1.2)
    ax.plot([xs[5], xs[6] + w], [0.30, 0.30], color="#94a3b8", lw=1.2)
    ax.text((xs[0] + xs[1] + w)/2, 0.275, "Planning & Validation", ha="center", va="top", fontsize=8.8, color="#334155")
    ax.text((xs[2] + xs[4] + w)/2, 0.275, "Execution", ha="center", va="top", fontsize=8.8, color="#334155")
    ax.text((xs[5] + xs[6] + w)/2, 0.275, "Post-Processing", ha="center", va="top", fontsize=8.8, color="#334155")

    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
