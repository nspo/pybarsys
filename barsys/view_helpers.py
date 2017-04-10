from .models import StatsDisplay, Purchase
from django.utils import timezone


def get_renderable_stats_elements():
    """Create a list of dicts for all StatsDisplays that can be rendered by view more easily"""
    stats_elements = []

    all_displays = StatsDisplay.objects.order_by("-show_by_default")
    for index, stat in enumerate(all_displays):
        stats_element = {"stats_id": "stats_{}".format(stat.pk),
                         "show_by_default": stat.show_by_default,
                         "title": stat.title}

        # construct query filters step by step
        filters = {}
        if stat.filter_category:
            filters["product_category"] = stat.filter_category.name
        if stat.filter_product:
            filters["product_name"] = stat.filter_product.name

        # filter by timedelta
        filters["created_date__gte"] = timezone.now() - stat.time_period

        stats_element["rows"] = []
        if stat.sort_by_and_show == StatsDisplay.SORT_BY_NUM_PURCHASES:
            top_five = Purchase.objects.stats_purchases_by_user(**filters)[:5]
            for user, total_quantity in top_five:
                stats_element["rows"].append({"left": "{}x".format(total_quantity),
                                              "right": "{} {}".format(stat.row_string, user.display_name)})
        else:
            top_five = Purchase.objects.stats_cost_by_user(**filters)[:5]
            for u_index, (user, total_cost) in enumerate(top_five):
                stats_element["rows"].append({"left": "{}.".format(u_index + 1),
                                              "right": "{} {}".format(stat.row_string, user.display_name)})

        if index + 1 < len(all_displays):
            # toggle next one on
            stats_element["toggle_other_on"] = "stats_{}".format(all_displays[index + 1].pk)
        else:
            # toggle first one on
            stats_element["toggle_other_on"] = "stats_{}".format(all_displays[0].pk)
        # if there is only one display, it's toggled off and on again with one click

        stats_elements.append(stats_element)

    return stats_elements
