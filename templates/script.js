
if (!String.prototype.format) {
	String.prototype.format = function () {
		var args = arguments;
		return this.replace(/{(\d+)}/g, function (value, idx) {
								return typeof args[idx] !== 'undefined' ? args[idx] : value;
							});
	};
}

