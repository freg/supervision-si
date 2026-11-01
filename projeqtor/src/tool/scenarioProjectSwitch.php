<?php
require_once "../tool/projeqtor.php";
$operation=RequestHandler::getValue('operation',true);
$project=RequestHandler::getValue('project',true);
$status=RequestHandler::getValue('status',($operation=='type')?true:false);
$delay=RequestHandler::getValue('delay',($operation=='delay')?true:false);

$result="OK";
$message="No error for operation=$operation, project=$project";
$altered='?';

$prj=new Project($project);
$typeProject=SqlList::getFieldFromId('ProjectType', $prj->idProjectType, 'code');
$crit=array('idProject'=>$project,'idUser'=>getCurrentUserId(),'idScenario'=>null);
$crsp=SqlElement::getSingleSqlElementFromCriteria('CriticalResourceScenarioProject', $crit);
if ($crsp->proposale==0) $crsp->proposale=null;
if ($operation=='type') {
  $newStatus=($status=='Locked')?'UnLocked':'Locked';
  if ($crsp->proposale!=null) {
    $crsp->proposale=null;
    $newStatus=($typeProject=='PRP')?'Locked':'UnLocked';
    $altered='NO';
  } else {
    $crsp->proposale=($typeProject=='PRP')?2:1;
    $newStatus=($typeProject=='PRP')?'UnLocked':'Locked';
    $altered='YES';
  }
  if ($crsp->proposale==null and $crsp->monthDelay==null) {
    $resSave=$crsp->delete();
  } else {
    $resSave=$crsp->save();
  }
  $result=getLastOperationStatus($resSave);
  if ($result!='OK') $message=strip_tags($resSave);
  echo '{"result":"'.$result.'","message":"'.$message.'", "newstatus":"'.$newStatus.'", "altered":"'.$altered.'"}';
} else if ($operation=='delay') {
  if (! $delay) $delay=null;
  $crsp->monthDelay=$delay;
  $altered=($delay)?'YES':'NO';
  if ($crsp->proposale==null and $crsp->monthDelay==null) {
    $resSave=$crsp->delete();
  } else {
    $resSave=$crsp->save();
  }
  $result=getLastOperationStatus($resSave);
  if ($result!='OK') $message=strip_tags($resSave).$delay;
  echo '{"result":"'.$result.'","message":"'.$message.'", "altered":"'.$altered.'"}';
} else {
  echo '{"result":"ERROR","message":"unexpected operation \''.$operation.'\'", "newstatus":"", "altered":""}';
}