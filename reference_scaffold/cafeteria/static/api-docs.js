document.addEventListener('DOMContentLoaded', function () {
  window.SwaggerUIBundle({
    url: '/api/v1/openapi.json',
    dom_id: '#swagger-ui',
    deepLinking: true,
    presets: [SwaggerUIBundle.presets.apis],
    layout: 'BaseLayout',
    tryItOutEnabled: true,
    plugins: [function () {
      return {
        wrapComponents: {
          authorizeBtn: function (Original, system) {
            return function (props) {
              return system.React.createElement(Original, Object.assign({}, props, {
                getComponent: function (name) {
                  // Keep Swagger's popup and event handling; render auth state as text.
                  if (name === 'LockAuthIcon' || name === 'UnlockAuthIcon') {
                    return function () { return props.isAuthorized ? ' (authorized)' : null; };
                  }
                  return props.getComponent.apply(null, arguments);
                },
              }));
            };
          },
        },
      };
    }],
  });
});
