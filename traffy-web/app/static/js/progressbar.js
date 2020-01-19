var bar = new ProgressBar.Circle(".progress-box", {
  color: "#6d767e",
  strokeWidth: 4,
  trailWidth: 1,
  easing: "easeInOut",
  duration: 1200,
  text: {
    autoStyleContainer: false
  },
  from: { color: "#aaa", width: 1 },
  to: { color: "#2d3748", width: 3 },
  step: function(state, circle) {
    circle.path.setAttribute("stroke", state.color);
    circle.path.setAttribute("stroke-width", state.width);

    var num = circle.value() * credit;
    var value = num.toFixed(2)
    if (value === 0) {
      circle.setText("");
    } else {
      circle.setText(value + " GiB");
    }

  }
});

bar.text.style.fontFamily = "Cantarell-Regular";
bar.text.style.fontSize = "20px";

oneValue = 1 / credit

bar.animate(volumeLeft * oneValue);
