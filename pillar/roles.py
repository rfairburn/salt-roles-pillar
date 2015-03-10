# -*- coding: utf-8 -*-
'''
Implements roles and categories removing the need for them in grains.
'''

from __future__ import absolute_import

# Import libs
import logging
import yaml
from salt.utils import fopen

# Set up logging
log = logging.getLogger(__name__)


def _parse_categories(all_cats_dict, to_parse_cats, applied_cats):
    '''
    Iterate through categories to inherit roles and other data.

    '''

    for category in to_parse_cats:
        if category not in applied_cats:
            applied_cats.append(category)
            # obtain the subcategories of the category to parse nested.
            more_cats = all_cats_dict.get(category, {}).get('categories', [])
            # recurse to get what we don't yet have.
            applied_cats = _parse_categories(
                all_cats_dict,
                more_cats,
                applied_cats
            )
    return applied_cats


def _parse_other(minion_id, all_roles_dict, categories):
    '''
    Look through all the parsed categories and apply any role or dict data
    that is not a category now that we've looked at all nested categories.
    '''
    other_dict = all_roles_dict['systems'].get(minion_id, {})
    if 'categories' in other_dict:
        del other_dict['categories']
    for category in categories:
        category_dict = all_roles_dict['categories'][category]
        # remove categories from the dict as we have a list of categories
        # that we want to work with already.
        if 'categories' in category_dict:
            del category_dict['categories']
        # This should work for roles, sudoers.included, and any other future
        # piece of information we want to be inheritable.
        for key, values in category_dict.items():
            if key in other_dict:
                for value in values:
                    if value not in other_dict[key]:
                        other_dict[key].append(value)
            else:
                other_dict[key] = values
    # Pruning
    # We can prune from any key but categories as I don't feel like killing
    # all of the inheritence we just created.  We should do this here since
    # categories will not be attached yet.

    for key, values in (kv for kv in other_dict.items()
                        if kv[0].startswith('prune_')):
        prune_key = key.replace('prune_', '')
        if prune_key in other_dict:
            other_dict[prune_key] = [v for v in other_dict[prune_key]
                                     if v not in values]
    return other_dict


def _generate_roles(minion_id, all_roles_dict):
    '''
    Generate the config roles and categories based on the entire roles dict.

    This should have category inheritence similar to the grains formula used
    previously.  A host will have categories and roles and can also inherit
    categories and roles from another category.
    '''

    try:
        all_cats_dict = all_roles_dict.get('categories', {})
        to_parse_cats = all_roles_dict.get('systems', {}).get(
            minion_id, all_cats_dict.get('default', {})
        ).get('categories', [])
        categories = _parse_categories(
            all_cats_dict,
            to_parse_cats,
            []
        )

        roles = _parse_other(minion_id, all_roles_dict, categories)
        roles.update({'categories': categories})

    except Exception:
        log.critical('Failed to generate roles')
        return {}

    return roles


def ext_pillar(minion_id,
               pillar,
               config_file='/srv/salt/ext_pillar/roles.yaml'):
    '''
    Load the yaml config to be used to generate roles.  Have _generate_roles()
    process them and return the result.
    '''

    try:
        with fopen(config_file, 'r') as config:
            all_roles_dict = yaml.safe_load(config)
    except Exception:
        log.critical('Failed to load yaml from {0}.'.format(config_file))
        return {}
    return _generate_roles(minion_id, all_roles_dict)
