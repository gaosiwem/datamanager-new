import { createElement } from 'react';
import { render } from 'react-dom';
import Homepage from '../views/Homepage';
import polyfillHTMLElementDataset from '../helpers/polyfillHTMLElementDataset';

polyfillHTMLElementDataset();

const node = document.querySelector('[data-webapp="homepage-hero"]');

const connection = () => {
  if (node) {
    const props = {
      image: 'https://via.placeholder.com/150',
      heading: node.dataset.mainHeading,
      subheading: node.dataset.subHeading,
      buttons: {
        primary: {
          text: node.dataset.primaryButtonLabel,
          link: node.dataset.primaryButtonUrl,
          target: node.dataset.primaryButtonTarget,
        },
        secondary: {
          text: node.dataset.secondaryButtonLabel,
          link: node.dataset.secondaryButtonUrl,
          target: node.dataset.secondaryButtonTarget,
        },
      },
      callToAction: {
        subheading: node.dataset.callToActionSubHeading,
        heading: node.dataset.callToActionHeading,
        link: {
          text: node.dataset.callToActionLinkLabel,
          link: node.dataset.callToActionLinkUrl,
          target: node.dataset.calToActionLinkTarget,
        },
      },
    };
    render(createElement(Homepage, props), node);
  }
};

export default connection();
