<?php
require_once "../tool/projeqtor.php";

$pool=RequestHandler::getValue('pool',true);
$date=RequestHandler::getValue('date',true);
$result="OK";
$altered='?';
//$pool=new ResourceTeam($pool);
$crit=array('idResource'=>$pool,'idUser'=>getCurrentUserId(),'idScenario'=>null,);
$crsp=SqlElement::getSingleSqlElementFromCriteria('CriticalResourceScenarioPool', $crit);
  if ($date) {
    $altered='YES';
    $crsp->givenDate=$date;
    $resSave=$crsp->save();
  } else  if ($crsp->id) {
    $altered='NO';
    $resSave=$crsp->delete();
  }
  $result=getLastOperationStatus($resSave);
  echo '{"result":"'.$result.'", "altered":"'.$altered.'"}';