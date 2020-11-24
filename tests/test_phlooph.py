from unittest import mock

import phlooph


def get_args_side_effect(*args, **kwargs):
    return mock.Mock(
        verbosity="fake-verbosity",
        dry_run="fake-dryrun",
    )


@mock.patch("phlooph.tag")
@mock.patch("phlooph.paginate")
@mock.patch("phlooph.render")
@mock.patch("phlooph.setup_logging")
@mock.patch("phlooph.get_args", side_effect=get_args_side_effect)
def test_main(mock_get_args, mock_setup_logging, mock_render, mock_paginate, mock_tag):
    phlooph.main()
    mock_get_args.assert_called_once()
    mock_setup_logging.assert_called_once_with("fake-verbosity")
    mock_render.assert_called_once_with("fake-dryrun")
    mock_paginate.assert_called_once_with("fake-dryrun")
    mock_tag.assert_called_once_with("fake-dryrun")
