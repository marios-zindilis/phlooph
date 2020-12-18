from unittest import mock

import phlooph


def get_args_side_effect_all_defaults(*args, **kwargs):
    """Return a mock object that looks like `argparse.Namespace`, with all default values."""
    return mock.Mock(
        verbosity=0,
        dry_run=False,
        skip_rendering=False,
        skip_pagination=False,
        skip_tagging=False,
        skip_feed=False,
    )


@mock.patch("phlooph.generate_feeds")
@mock.patch("phlooph.tag")
@mock.patch("phlooph.paginate")
@mock.patch("phlooph.render")
@mock.patch("phlooph.setup_logging")
@mock.patch("phlooph.get_args", side_effect=get_args_side_effect_all_defaults)
def test_main(
    mock_get_args,
    mock_setup_logging,
    mock_render,
    mock_paginate,
    mock_tag,
    mock_generate_feeds,
):
    phlooph.main()
    mock_get_args.assert_called_once()
    mock_setup_logging.assert_called_once_with(0)
    mock_render.assert_called_once_with(False)
    mock_paginate.assert_called_once_with(False)
    mock_tag.assert_called_once_with(False)
    mock_generate_feeds.assert_called_once_with(False)
