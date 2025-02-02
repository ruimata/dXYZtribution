import bpy
import mathutils
from functools import partial
from bpy.props import *
from operator import (
    itemgetter,
)  # faster sorting compared to lambda (as it apparently uses C)

EVEN_ORIGINS = "0"
EVEN_GAPS = "1"


class OBJECT_PT_distribution_panel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_distribution_panel"
    bl_label = "dXYZtribution options"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "dXYZtribution"

    def draw(self, context):
        gap_choice = False

        layout = self.layout
        layout.label(text="Distribution Options")

        if bpy.context.selected_objects.__len__() < 2:
            layout.separator()
            layout.label(text="Select at least 2 objects")
            layout.separator()
            return
        elif bpy.context.selected_objects.__len__() == 2:
            sub_layout = layout.row()
            sub_layout.enabled = False
            sub_layout.prop(
                context.scene,
                "positional",
                text="within max/min positions",
            )
        else:
            gap_choice = True
            layout.prop(
                context.scene,
                "positional",
                text="within max/min positions",
            )

        # gap float can only be  available when positional  is false (even gaps)  or when only two
        # objects are selected (nothing to  distribute in terms of origins  as max and min will be
        # stationary by definition). To distributed based on gaps, a min of 3 objects is required.
        if not context.scene.positional or not gap_choice:
            layout.prop(context.scene, "gap_size", text="Gap", expand=False)

        axis = layout.box()
        axis.prop(
            context.scene,
            "axyz",
            text="'aXYZ'",
            toggle=True,
        )

        layout.prop(context.scene, "target", text="Target", expand=True)

        row = layout.row()
        row.scale_y = 1.5
        row.enabled = any(context.scene.axyz)
        row.operator("bl_apply.distribution", text="Apply", icon="MOD_ARRAY")


class OBJECT_OT_distribution(bpy.types.Operator):
    bl_idname = "object.distribution"
    bl_label = "Distribution"
    bl_options = {"REGISTER", "UNDO"}

    bpy.types.Scene.positional = bpy.props.BoolProperty(
        description="use original object's positions, in each axis, and use objects at max and min positions as references and distribute all other objects between them. If not selected, user must specify an intended separation between objects.",
        default=True,
    )
    bpy.types.Scene.axyz = bpy.props.BoolVectorProperty(
        default=(False, False, False),
        size=3,
        subtype="XYZ",
        description="Distribution will apply to selected axis individually",
    )  # 0: X, 1: Y, 2: Z
    bpy.types.Scene.target = EnumProperty(
        name="target",
        items=[("0", "Even Origins", ""), ("1", "Even Gaps", "")],
        default=0,
        description="Even Origins: Applying distribution to objects' origin will generate different gaps, depending on object sizes, in a specific axis (ensuring all origins will be equidistant).\n\nEven Gaps: Selecting even gaps will ensure the separation between objects is the same, for selected axis.\n\n",
    )
    bpy.types.Scene.gap_size = bpy.props.FloatProperty(
        name="Gap Size", default=1, min=0, step=1, precision=3
    )

    bpy.types.Scene.apply = bpy.props.BoolProperty(
        name="Apply", description="Apply distribution", default=False
    )

    def execute(self, context):
        return {"FINISHED"}


class ApplyDistribution(bpy.types.Operator):
    bl_idname = "bl_apply.distribution"
    bl_label = "Apply Distribution"
    bl_description = "Apply distribution settings to selected objects"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        selected = bpy.context.selected_objects  # create vector with selected objects
        for axis, value in enumerate(
            context.scene.axyz
        ):  # create vectors with object's coordinated per selected axis
            if value:
                coordinates = get_coordinates(selected, axis)
                if (
                    context.scene.positional
                    and context.scene.target == EVEN_GAPS
                    and get_total_distance(coordinates)
                    < get_space_filled_between_objects(coordinates, axis)
                ):
                    self.report(
                        {"ERROR"},
                        "Not enough space to distribute objects in the selected axis",
                    )
                    return {"CANCELLED"}

                apply_translations(
                    coordinates,
                    axis,
                    context.scene.positional,
                    context.scene.target,
                    context.scene.gap_size,
                )

        # disable UI (turn axis's toggles off), so user must understand he's required to chose again
        context.scene.axyz = (False, False, False)
        return {"FINISHED"}


def get_coordinates(objs, axis):
    return sorted([(o.location[axis], o) for o in objs], key=itemgetter(0))


def get_total_distance(sorted_objs):
    return sorted_objs[-1][0] - sorted_objs[0][0]


def get_partial_distance(sorted_objs):
    return get_total_distance(sorted_objs) / (len(sorted_objs) - 1)


def get_min_max_positions(obj, axis):
    coord = [v.co[axis] * obj.scale[axis] for v in obj.data.vertices]
    return (min(coord), max(coord))


def get_space_filled_between_objects(sorted_objs, axis):
    dimensions = [(get_min_max_positions(o[1], axis)) for o in sorted_objs]
    return (
        abs(dimensions[0][1])
        + sum([abs(d[0]) + abs(d[1]) for d in dimensions[1:-1]])
        + abs(dimensions[-1][0])
    )


def apply_translations(sorted_objs, axis, positional, apply_to, gap_size):
    # gap = get_partial_distance(sorted_objs) if positional else gap_size
    if positional:
        if apply_to == EVEN_ORIGINS:
            gap = get_partial_distance(sorted_objs)
        else:
            gap = (
                get_total_distance(sorted_objs)
                - get_space_filled_between_objects(sorted_objs, axis)
            ) / (len(sorted_objs) - 1)
    else:
        gap = gap_size

    for idx, item in enumerate(sorted_objs):
        if idx == 0:
            continue
        if apply_to == EVEN_ORIGINS:
            item[1].location[axis] = sorted_objs[idx - 1][1].location[axis] + gap
        else:
            item[1].location[axis] = (
                sorted_objs[idx - 1][1].location[axis]
                + abs(get_min_max_positions(sorted_objs[idx - 1][1], axis)[1])
                + gap
                + abs(get_min_max_positions(item[1], axis)[0])
            )


def register():
    bpy.utils.register_class(OBJECT_OT_distribution)
    bpy.utils.register_class(OBJECT_PT_distribution_panel)
    bpy.utils.register_class(ApplyDistribution)


def unregister():
    bpy.utils.register_class(OBJECT_OT_distribution)
    bpy.utils.register_class(OBJECT_PT_distribution_panel)
    bpy.utils.register_class(ApplyDistribution)


bl_info = {
    "name": "dXYZtribution",
    "description": "Automatically distribute objects in space",
    "author": "atamiur",
    "version": (0, 1, 0),
    "blender": (2, 80, 0),
    "location": "Text Editor > Auto Load",
    "warning": "",
    "wiki_url": "",
    "category": "UI",
}

if __name__ == "__main__":
    register()
