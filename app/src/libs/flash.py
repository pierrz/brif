"""
Flash messages: an endpoint that redirects leaves a message in the session, the next page that is
rendered shows it once (get_messages() of the templates).

These are the two functions of starlette-core that the app used, which has had no release since 2021
and no commit since 2022 and pulled SQLAlchemy and WTForms in for nothing. Needs the SessionMiddleware.
"""

import typing

from starlette.requests import Request


def message(request: Request, text: typing.Any, category: str = "default") -> None:
    """
    Queue a message for the next page
    :param request: the current request
    :param text: the message
    :param category: its category, the 'message-<category>' class of the page ('success', ...)
    :return: does its thing
    """
    if "_messages" not in request.session:
        request.session["_messages"] = []
    request.session["_messages"].append({"message": text, "category": category})


def get_messages(request: Request) -> typing.List[typing.Dict[str, typing.Any]]:
    """
    Take the queued messages out of the session
    :param request: the current request
    :return: the messages, each one {"message": ..., "category": ...}
    """
    return request.session.pop("_messages") if "_messages" in request.session else []
