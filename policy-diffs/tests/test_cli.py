from pathlib import Path

from pipeline.cli import build_arg_parser


def test_cli_has_run_phase_and_render_subcommands():
    parser = build_arg_parser()
    args = parser.parse_args(["render-site", "--artifact", "spme"])
    assert args.cmd == "render-site"
    args = parser.parse_args(["run-phase", "--artifact", "spme"])
    assert args.cmd == "run-phase"
