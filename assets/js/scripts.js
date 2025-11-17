import "../scss/styles.scss";

import "classlist-polyfill";
import "whatwg-fetch";
import "url-search-params-polyfill";

import "jquery";
import "bootstrap/js/dist/scrollspy.js";

import "./utilities/js/modules/loadStringQueries.js";
import "./utilities/js/modules/createComponentInterfaces.js";
import "./utilities/js/modules/polyfillOldFeatures.js";
import "./utilities/js/embedding/datawrapper.js";
import "./utilities/js/helpers/formatLargeValues.js";

import "./components/search-results/SearchResult/scripts.js";

import "./components/learning-centre/Glossary/scripts.jsx";

import "./components/homepage/ValueBlocks/scripts.jsx";
import "./components/homepage/Revenue/scripts.jsx";
import "./components/homepage/HomeChart/scripts.jsx";
import "./components/homepage/Showcase/scripts.jsx";

import "./components/header-and-footer/Search/scripts.jsx";
import "./components/header-and-footer/Search/index.jsx";
import "./components/header-and-footer/YearSelect/scripts.jsx";
import "./components/header-and-footer/SubLinks/scripts.js";
import "./components/header-and-footer/NavBar/scripts.js";
import "./components/header-and-footer/Modals/scripts.jsx";

import "./components/department-budgets/DeptSearch/scripts.jsx";
import "./components/department-budgets/IntroSection/scripts.jsx";
import "./components/department-budgets/ArrowButtons/scripts.js";
import "./components/department-budgets/PerformanceIndicators/scripts.jsx";

import "./components/public-entity-budgets/PublicEntitySearch/scripts.jsx";
import "./components/public-entity-budgets/scripts.jsx";
import "./components/public-entity-budgets/IntroSection/scripts.jsx";
import "./components/public-entity-budgets/ArrowButtons/scripts.js";
import "./components/public-entity-budgets/PerformanceIndicators/scripts.jsx";

import "./components/public-entity-budgets/IntroSection/index.jsx";

import "./components/performance/Table/scripts.jsx";

import "./components/contributed-data/CsoMeta/scripts.js";

import "./components/budget-summary/budget-summary.js";
import "./components/budget-summary/consolidated-detailed/index.js";
import "./components/budget-summary/national-provincial-detailed/index.js";

import "./components/universal/Button/scripts.js";
import "./components/universal/ResponsiveChart/scripts.jsx";
import "./components/universal/Comments/scripts.js";
import "./components/universal/Participate/scripts.jsx";
import "./components/universal/Tooltip/scripts.js";
import "./components/universal/VideoCard/scripts.js";
import "./components/universal/ThumbPreview/scripts.js";

import "./services/chartAdaptor/scripts.js";
import "./scenes/department/AdjustedSection/components/ChangeIndicator/scripts.js";
import "./scenes/department/ProgramEconSmallMultiples/programme-econ-small-muls.js";
import "./components/Share/scripts.js";
import "./scenes/homepage/Hero/scripts.js";
import "./scenes/department/ProgrammesSection/index.js";
import "./scenes/department/EconClassPackedCircles/econ-class-packed-circles.js";
import "./scenes/department/ProgramEconSmallMultiples/programme-econ-small-muls.js";
import "./scenes/department/ExpenditureSection/expenditure-section.js";
import "./scenes/department/ExpenditurePhaseSection/expenditure-phase-section.js";
import "./scenes/department/ExpenditureMultiplesSection/expenditure-multiples-section.js";

import "./embeds/equitable-share/index.js";
import "./embeds/chart-bubbles/index.js";
import "./embeds/chart-treemap/index.js";

window.onload = function() {
  window.scrollTo(0, 0); // Reset scroll position to the top-left
};
