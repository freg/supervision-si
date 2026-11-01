<?php 
// Script à passer 
// INSERT INTO `${prefix}report` (`id`, `name`, `idReportCategory`, `file`, `sortOrder`, `hasExcel`,`hasPdf`,`hasToday`) VALUES (133, 'reportChartJS', 10, 'testChartJs.php', 1050,0,0,0);
// INSERT INTO `${prefix}habilitationreport` (`idProfile`, `idReport`, `allowAccess`) VALUES (1, 133, 1);
include_once '../tool/projeqtor.php';
include_once "../tool/jsonFunctions.php";
$headerParameters = "";
include "header.php";
$print=true;
if (isset($_REQUEST['xhrPostDestination'])) $print=($_REQUEST['xhrPostDestination']=='detailReportDiv')?false:true;
?>

<div class="container" dojoType="dijit.layout.BorderContainer" id="internalReportContainer" >
  <div dojoType="dijit.layout.ContentPane" region="center" style="">
    <div style="width:80%;height:400px;border:1px solid grey;margin-left:10%;margin-top:<?php echo ($print)?50:20;?>px">
    <canvas id="reportChartTest" class="reportChart" style="height:300px;width:80%"></canvas>
    </div>
    <script type="dojo/connect" event="resize" args="evt">
Chart.register(ChartDataLabels);
const ctx = document.getElementById('reportChartTest');
const myChart = new Chart(ctx, {
  type: 'bar',
  data: {
      labels: ['Red', 'Blue', 'Yellow', 'Green', 'Purple', 'Orange'],
      datasets: [{
          label: '# of Votes',
          data: [12, 19, 3, 5, 2, 3],
          backgroundColor: [
              'rgba(255, 99, 132, 0.2)',
              'rgba(54, 162, 235, 0.2)',
              'rgba(255, 206, 86, 0.2)',
              'rgba(75, 192, 192, 0.2)',
              'rgba(153, 102, 255, 0.2)',
              'rgba(255, 159, 64, 0.2)'
          ],
          borderColor: [
              'rgba(255, 99, 132, 1)',
              'rgba(54, 162, 235, 1)',
              'rgba(255, 206, 86, 1)',
              'rgba(75, 192, 192, 1)',
              'rgba(153, 102, 255, 1)',
              'rgba(255, 159, 64, 1)'
          ],
          borderWidth: 2
      }]
  },
  options: {
      scales: {
          y: {
              beginAtZero: true
          }
      },
      plugins: {
        // Change options for ALL labels of THIS CHART
        datalabels: {
          color: [
              'rgba(255, 99, 132, 1)',
              'rgba(54, 162, 235, 1)',
              'rgba(255, 206, 86, 1)',
              'rgba(75, 192, 192, 1)',
              'rgba(153, 102, 255, 1)',
              'rgba(255, 159, 64, 1)'
          ]
        }
      }
    
  }
});
         </script>
  </div>
</div>   