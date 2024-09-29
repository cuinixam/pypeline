from unittest.mock import Mock, call

from pypeline.steps.west_install import WestInstall


def test_west_install(execution_context: Mock) -> None:
    west_install = WestInstall(execution_context, "group_name")
    west_install.run()

    # Expected calls
    expected_calls = [
        call(
            [
                "west",
                "init",
                "-l",
                "--mf",
                execution_context.project_root_dir.joinpath("west.yaml").as_posix(),
                execution_context.project_root_dir.joinpath("build/west").as_posix(),
            ],
            cwd=execution_context.project_root_dir,
        ),
        call().execute(),
        call(["west", "update"], cwd=execution_context.project_root_dir / "build"),
        call().execute(),
    ]

    execution_context.create_process_executor.assert_has_calls(expected_calls)
