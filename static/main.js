var radios = document.getElementsByName('option');
var cellRadios = document.getElementsByName('cell');
var strainRadios = document.getElementsByName('strain');
var otherInput = document.getElementById('inputOther');
var otherCellInput = document.getElementById('inputOtherCell');
var otherStrainInput = document.getElementById('inputOtherStrain');

var publishDateRadios = document.getElementsByName('publishDate');
var datePickers = document.getElementById('datePickers');
var setDates = document.getElementById('setDates');
var startDatePicker = document.getElementById('startDate');
var endDatePicker = document.getElementById('endDate');
var customDatesLabel = document.getElementById('customDatesLabel');

var extraInputs = document.getElementsByClassName('extraInput');

for (var i = 0; i < radios.length; i++) {
    radios[i].addEventListener('change', function() {
        for (var j = 0; j < extraInputs.length; j++) {
            if (radios[j].checked) {
                extraInputs[j].style.display = 'inline-block';
            } else {
                extraInputs[j].style.display = 'none';
                extraInputs[j].value = '';
            }
        }
    });
}


for (var i = 0; i < radios.length; i++) {
    radios[i].addEventListener('change', function() {
        if (document.getElementById('otherCheck').checked) {
            otherInput.style.display = 'inline-block';
        } else {
            otherInput.style.display = 'none';
            otherInput.value = '';
        }
    });
}

for (var i = 0; i < cellRadios.length; i++) {
    cellRadios[i].addEventListener('change', function() {
        if (document.getElementById('otherCellCheck').checked) {
            otherCellInput.style.display = 'inline-block';
        } else {
            otherCellInput.style.display = 'none';
            otherCellInput.value = '';
        }
    });
}

for (var i = 0; i < strainRadios.length; i++) {
    strainRadios[i].addEventListener('change', function() {
        if (document.getElementById('otherStrainCheck').checked) {
            otherStrainInput.style.display = 'inline-block';
        } else {
            otherStrainInput.style.display = 'none';
            otherStrainInput.value = '';
        }
    });
}


datePickers.style.display = 'none';

for (var i = 0; i < publishDateRadios.length; i++) {
    publishDateRadios[i].addEventListener('change', function() {
        if (document.getElementById('customDates').checked) {
            datePickers.style.display = 'inline-block';
        } else {
            datePickers.style.display = 'none';
            startDatePicker.value = '';
            endDatePicker.value = '';
            customDatesLabel.innerHTML = 'Custom dates';
        }
    });
}

setDates.addEventListener('click', function() {
    var startDate = startDatePicker.value;
    var endDate = endDatePicker.value;

    if (startDate && endDate) {
        customDatesLabel.innerHTML = `Custom dates (${startDate} - ${endDate})`;
    }
});


window.onload = function() {
    document.getElementById('downloadBtn').addEventListener('click', function() {
        var doc = new jsPDF('p', 'pt');
        doc.autoTable({
            html: '#outputTable',
            theme: 'striped'
        });
        doc.save('table.pdf');
    });
}

