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
$currency=Parameter::getGlobalParameter('currency');
$tabData = array();
$globalTopTab= array();
$proj = new Project();
$lstProj = $proj->getSqlElementsFromCriteria(array('codeType'=>'PRP','idle'=>'0'));
$i = 0;
$y = 0;
$a = 0;
$avgValue = 0;
$maxValue = 0;
$maxSize = 0;

$minX= 100;
$minY = 100;

foreach ($lstProj as $pro){
  if($pro->ProjectPlanningElement->totalValidatedCost){
    $a++;
  }else{
    continue;
  }
  $avgValue += $pro->ProjectPlanningElement->totalValidatedCost;
  if($maxValue < $pro->ProjectPlanningElement->totalValidatedCost)$maxValue = $pro->ProjectPlanningElement->totalValidatedCost;
}
if($a > 0){
  $avgValue = $avgValue / $a;
  $maxSize = max($maxValue,2*$avgValue);
}

foreach ($lstProj as $pro){
  $tabData[$pro->id]['label'] = htmlEncode($pro->name,"quotes");;
  $tabData[$pro->id]['x'] = $pro->strategicValue;
  $tabData[$pro->id]['cost'] = $pro->ProjectPlanningElement->totalValidatedCost;
  $tabData[$pro->id]['idproj'] = $pro->id;
  if(!$tabData[$pro->id]['cost'])$tabData[$pro->id]['cost'] = 0;
  $benefit =($pro->benefitValue)?$pro->benefitValue:0;
  $tabData[$pro->id]['y'] = $benefit;
  if($maxSize){
    $size = $pro->ProjectPlanningElement->totalValidatedCost/$maxSize*100;
  }else{
    $size = 10;
  }
  if($size > 100)$size = 100;
  if($size < 10)$size = 10;
  $tabData[$pro->id]['r'] = round($size,2);
  $riskLevel = new RiskLevel($pro->idRiskLevel);
  $color=($riskLevel->color)?$riskLevel->color:'#D3D3D3';
  $tabData[$pro->id]['borderColor'] = $color; 
  $tabData[$pro->id]['backgroundColor'] = $color;
  $i++;
  if($minX > $pro->strategicValue)$minX=$pro->strategicValue;
  if($minY > $benefit)$minY=$benefit;
  if($pro->idRiskLevel){
    $riskLevelObj = new RiskLevel($pro->idRiskLevel);
    $nameRisk = $riskLevelObj->name;
  }else{
    $riskLevelObj = new RiskLevel();
    $nameRisk = i18n('noDataFound');
  }
  $tabData[$pro->id]['risk']=$nameRisk;
  $globalTopTab[$riskLevelObj->sortOrder][$nameRisk][$pro->id] = $tabData[$pro->id];
}
ksort($globalTopTab);
$minY = $minY-10;
$minX = $minX -10;


function adjustBrightness($hexCode, $adjustPercent) {
  $hexCode = ltrim($hexCode, '#');

  if (strlen($hexCode) == 3) {
    $hexCode = $hexCode[0] . $hexCode[0] . $hexCode[1] . $hexCode[1] . $hexCode[2] . $hexCode[2];
  }

  $hexCode = array_map('hexdec', str_split($hexCode, 2));

  foreach ($hexCode as & $color) {
    $adjustableLimit = $adjustPercent < 0 ? $color : 255 - $color;
    $adjustAmount = ceil($adjustableLimit * $adjustPercent);

    $color = str_pad(dechex($color + $adjustAmount), 2, '0', STR_PAD_LEFT);
  }

  return '#' . implode($hexCode);
}

function getOpacityBackground($hexCode){
  $tabColor = hex2rgb($hexCode);
  return  'rgba('.$tabColor['R'].', '.$tabColor['G'].', '.$tabColor['B'].', 0.2)';
}

?>

<div class="container" dojoType="dijit.layout.BorderContainer" id="internalReportContainer2" >
  <div dojoType="dijit.layout.ContentPane" region="center" style="">
    <div style="width:80%;height:80%;min-height:400px;border:1px solid grey;margin-left:10%;margin-top:<?php echo ($print)?50:20;?>px">
      <canvas id="reportProposal" class="reportChart" style="min-height:300px;height:80%;width:80%"></canvas>
    </div>
    <script type="dojo/connect" event="resize" args="evt">
      Chart.register(ChartDataLabels);
      const ctx = document.getElementById('reportProposal');
      var labels = ['label'];
      var data = {
        labels: labels,
        datasets: [
    <?php foreach ($globalTopTab as $globalTab){ ?>
      <?php foreach ($globalTab as $nameLevelRisk=>$tabByLevelRisk){ ?> 
         {
            label: '<?php echo $nameLevelRisk;?>',
            data: [
        <?php $nbTabValue = count($tabByLevelRisk); $nbTab = 1;?>
        <?php foreach ($tabByLevelRisk as $data){ ?>    
            {x: <?php echo $data['x']; ?>,y: <?php echo $data['y']; ?>,r: <?php echo $data['r']; ?> , name: '<?php echo $data['label']; ?>',idproj:'<?php echo $data['idproj']; ?>' , risk: '<?php echo $data['risk']; ?>'  , cost: <?php echo $data['cost']; ?> }
            <?php if($nbTab != $nbTabValue){ ?> , <?php } ?>
            <?php $nbTab++;   $colorTab = $data['borderColor']; $backGroundColor = adjustBrightness($data['backgroundColor'],0.6); $opacityBackground = getOpacityBackground($backGroundColor);?> 
        <?php } ?>
           ],
           borderColor: '<?php echo $colorTab;?>',
           backgroundColor: '<?php echo $opacityBackground;?>'
          } <?php if($y != $i){ ?> , <?php } ?>
       <?php } ?>
    <?php } ?>
       ],
      };

    var bubbleChart = new Chart(ctx, {
      type: 'bubble',
      data: data,
      options: {
        scales: {
          y : {
            display : true,
            suggestedMin: <?php echo $minY; ?>,
            title: { display: true, text: '<?php echo i18n('colBenefitValue');?>' }
          },
          x : {
            suggestedMin:  <?php echo $minX; ?>,
            display : true,
            title: { display: true, text: '<?php echo i18n('colStrategicValue'); ?>' }
          }
        },
       onClick: function(e) {
        var click = this.getActiveElements();
        gotoElement('Project',click[0].element.$context.raw.idproj,true);
      },
     plugins: {
      tooltip: {
       callbacks: {
        label: function(context) {
                var label = "<?php echo i18n('Project');?> : "+context.raw.name;
                var label2 = "<?php echo i18n('colStrategicValue');?> : "+context.raw.x;
                var label3 = "<?php echo i18n('colBenefitValue');?> : "+context.raw.y;
                var label4 = "<?php echo i18n('colTotalValidatedCost');?> : "+context.raw.cost +" <?php echo $currency;?>";
                var label5 = "<?php echo i18n('colRiskLevel');?> : "+context.raw.risk;
                return [label, label2 , label3 , label4, label5];
              }
        },
            
      },
      datalabels: {
        formatter: function(value, context) {
          return value.name;
        },
        anchor: function(context) {
          var value = context.dataset.data[context.dataIndex];
          return value.v < 50 ? 'end' : 'center';
        },
        align: function(context) {
          var value = context.dataset.data[context.dataIndex];
          return value.v < 50 ? 'end' : 'center';
        },
        color: function(context) {
          var value = context.dataset.data[context.dataIndex];
          return value.v < 50 ? context.dataset.backgroundColor : 'dark-grey';
        },
       
        font: {
          weight: 'bold'
        },
        offset: 2,
        padding: 0
      }
    }
      }
    });
    </script>
  </div>
</div>   