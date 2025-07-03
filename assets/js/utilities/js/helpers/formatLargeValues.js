// ✅ Function to format large numbers
function formatValue(value) {
  if (value >= 1e12) {
    return `R ${(value / 1e12).toFixed(1).toLocaleString()} trillion`; // Trillions
  } else if (value >= 1e9) {
    return `R ${(value / 1e9).toFixed(1).toLocaleString()} billion`; // Billions
  } else if (value >= 1e6) {
    return `R ${(value / 1e6).toFixed(1).toLocaleString()} million`; // million
  } else if (value >= 1e3) {
    return `R ${(value / 1e3).toFixed(1).toLocaleString()} thousand`; // thousand
  } else {
    return "R " + value.toLocaleString(); // Default formatting
  }
}
