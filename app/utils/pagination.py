from flask import request, url_for

PER_PAGE_OPTIONS = (10, 20, 25, 50, 100, 250)
DEFAULT_PER_PAGE = 20


def get_per_page(default=DEFAULT_PER_PAGE):
    """Read a safe page-size choice from query args."""
    value = request.args.get("per_page", default, type=int)
    if value in PER_PAGE_OPTIONS:
        return value
    return default


def pagination_url(page, per_page=None):
    """Build a current-route pagination URL while preserving active filters."""
    args = request.args.to_dict(flat=True)
    args["page"] = page
    if per_page is not None:
        args["per_page"] = per_page
    elif "per_page" not in args:
        args["per_page"] = get_per_page()
    return url_for(request.endpoint, **(request.view_args or {}), **args)
