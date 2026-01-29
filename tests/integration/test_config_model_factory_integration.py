import pytest

from src.services.config_model_factory import ConfigModelFactory


def test_create_from_schema_skips_cpp_expression_default() -> None:
    schema = {
        "amrex.the_arena_init_size": {
            "type": "long",
            "required": False,
            "is_array": False,
            "default": "Gpu::Device::totalGlobalMem() / Gpu::Device::numDevicePartners() / 4L * 3L",
            "source_file": "Src/Base/AMReX_Arena.cpp",
        }
    }

    model_class = ConfigModelFactory.create_from_schema(schema, build_config={})

    field = model_class.model_fields["amrex_the_arena_init_size"]
    assert field.default is None


def test_create_from_schema_skips_cpp_expression_default_min_call() -> None:
    schema = {
        "amrex.the_arena_init_size": {
            "type": "long",
            "required": False,
            "is_array": False,
            "default": "std::min(the_arena_init_size, Gpu::Device::maxMemAllocSize())",
            "source_file": "Src/Base/AMReX_Arena.cpp",
        }
    }

    model_class = ConfigModelFactory.create_from_schema(schema, build_config={})

    field = model_class.model_fields["amrex_the_arena_init_size"]
    assert field.default is None


def test_hydrate_skips_cpp_expression_value() -> None:
    schema = {
        "amrex.the_arena_init_size": {
            "type": "long",
            "required": False,
            "is_array": False,
            "default": None,
            "source_file": "Src/Base/AMReX_Arena.cpp",
        }
    }

    model_class = ConfigModelFactory.create_from_schema(schema, build_config={})

    inputs_text = "amrex.the_arena_init_size = std::min(the_arena_init_size, Gpu::Device::maxMemAllocSize())"
    model = ConfigModelFactory.hydrate(model_class, inputs_text)

    assert model.amrex_the_arena_init_size is None


def test_hydrate_handles_warpx_expression_patterns() -> None:
    schema = {
        "my_constants.nano": {
            "type": "Real",
            "required": False,
            "is_array": False,
            "default": None,
            "source_file": "Examples/Tests/nodal_electrostatic/inputs_test_3d_nodal_electrostatic_solver",
        },
        "my_constants.sigma": {
            "type": "Real",
            "required": False,
            "is_array": False,
            "default": None,
            "source_file": "Examples/Tests/nodal_electrostatic/inputs_test_3d_nodal_electrostatic_solver",
        },
        "my_constants.Lx": {
            "type": "Real",
            "required": False,
            "is_array": False,
            "default": None,
            "source_file": "Examples/Tests/nodal_electrostatic/inputs_test_3d_nodal_electrostatic_solver",
        },
        "amr.n_cell": {
            "type": "IntVect",
            "required": False,
            "is_array": True,
            "default": None,
            "source_file": "Examples/Tests/nodal_electrostatic/inputs_test_3d_nodal_electrostatic_solver",
        },
        "geometry.prob_lo": {
            "type": "RealVect",
            "required": False,
            "is_array": True,
            "default": None,
            "source_file": "Examples/Tests/nodal_electrostatic/inputs_test_3d_nodal_electrostatic_solver",
        },
        "warpx.eb_implicit_function": {
            "type": "string",
            "required": False,
            "is_array": False,
            "default": None,
            "source_file": "Examples/Tests/embedded_boundary_cube/inputs_base_3d",
        },
        "amrex.the_arena_init_size": {
            "type": "long",
            "required": False,
            "is_array": False,
            "default": "Gpu::Device::totalGlobalMem() / Gpu::Device::numDevicePartners() / 4L * 3L",
            "source_file": "Src/Base/AMReX_Arena.cpp",
        },
    }

    model_class = ConfigModelFactory.create_from_schema(schema, build_config={})

    inputs_text = "\n".join(
        [
            "my_constants.nano = 1e-9",
            "my_constants.sigma = 10*nano",
            "my_constants.Lx = 7*sigma",
            "my_constants.nx = 128",
            "my_constants.ny = 128",
            "my_constants.nz = 128",
            "amr.n_cell = nx ny nz",
            "geometry.prob_lo = -0.5*Lx -0.5*Ly -0.5*Lz",
            'warpx.eb_implicit_function = \"(x**2 + y**2 - R**2)\"',
        ]
    )

    with pytest.raises(Exception):
        ConfigModelFactory.hydrate(model_class, inputs_text)


def test_hydrate_with_cpp_default_expression_no_inputs() -> None:
    schema = {
        "amrex.the_arena_init_size": {
            "type": "long",
            "required": False,
            "is_array": False,
            "default": "std::min(the_arena_init_size, Gpu::Device::maxMemAllocSize())",
            "source_file": "Src/Base/AMReX_Arena.cpp",
        }
    }

    model_class = ConfigModelFactory.create_from_schema(schema, build_config={})
    model = ConfigModelFactory.hydrate(model_class, "")

    assert model.amrex_the_arena_init_size is None
