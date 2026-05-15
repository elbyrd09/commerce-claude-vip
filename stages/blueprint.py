import urllib.parse


def generate_blueprint(
    php_plugin_code: str,
    demo_title: str,
    block_slug: str,
) -> dict:
    """Build a WordPress Playground blueprint dict ready to be hosted and shared."""
    plugin_code = php_plugin_code

    return {
        "landingPage": "/wp-admin/post-new.php",
        "preferredVersions": {"php": "8.3", "wp": "latest"},
        "steps": [
            # Install Remote Data Blocks from wordpress.org
            {
                "step": "installPlugin",
                "pluginData": {
                    "resource": "wordpress.org/plugins",
                    "slug": "remote-data-blocks",
                },
            },
            # Create the plugin directory then write the file
            {
                "step": "mkdir",
                "path": "/wordpress/wp-content/plugins/demo-connector",
            },
            {
                "step": "writeFile",
                "path": "/wordpress/wp-content/plugins/demo-connector/demo-connector.php",
                "data": plugin_code,
            },
            # Activate the connector (RDB is auto-activated as a dependency)
            {
                "step": "activatePlugin",
                "pluginPath": "demo-connector/demo-connector.php",
            },
            # Brand the demo site
            {
                "step": "setSiteOptions",
                "options": {"blogname": f"Demo — {demo_title}"},
            },
            # Log in so the block editor is ready immediately
            {
                "step": "login",
                "username": "admin",
                "password": "password",
            },
        ],
    }


def playground_url(blueprint_url: str) -> str:
    """Return the WordPress Playground URL that loads a hosted blueprint."""
    encoded = urllib.parse.quote(blueprint_url, safe="")
    return f"https://playground.wordpress.net/?blueprint-url={encoded}"
