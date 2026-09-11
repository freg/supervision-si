<?php
include_once '../tool/projeqtor.php';
$user = getSessionUser(); if (! $user || ! $user->id) { htmlDisplayErrorAndDie(i18n('messageSessionWillExpire')); }
$projectId = RequestHandler::getId('projectId'); $sprintId  = RequestHandler::getId('sprintId'); $dateStr = RequestHandler::getValue('date'); $theDate = $dateStr ? $dateStr : date('Y-m-d');
$prefix = Parameter::getGlobalParameter('paramDbPrefix');
$spStart=null; $spEnd=null; if ($sprintId) { $sp=new Sprint($sprintId); if ($sp->id && $sp->SprintPlanningElement) { $spStart=$sp->SprintPlanningElement->plannedStartDate; $spEnd=$sp->SprintPlanningElement->plannedEndDate; } }
function html($s){ return htmlEncode($s,'html'); } function title($t){ echo "<h2 style='margin:12px 0 6px;'>".html($t)."</h2>"; }
function sqlAll($q){ $res=Sql::query($q); $rows=[]; while($r=Sql::fetchLine($res)) $rows[]=array_change_key_case($r, CASE_LOWER); return $rows; }
$yesterday = date('Y-m-d', strtotime($theDate.' -1 day'));
$doneWhereSprintUS = $sprintId ? " and us.idSprint=".Sql::fmtId($sprintId)." " : "";
$doneWhereSprintAC = ($spStart && $spEnd) ? " and pe.refType='Activity' and (pe.plannedStartDate<=".Sql::str($spEnd)." and pe.plannedEndDate>=".Sql::str($spStart).") " : "";
$doneUS = "select 'UserStory' as refType, us.id as refId, us.name, s.name as statusName, h.operationDate, u.fullName as who
  from ${prefix}history h join ${prefix}status s on s.id = CAST(h.newValue as UNSIGNED) and s.setIdleStatus=1
  join ${prefix}userstory us on us.id = h.refId left join ${prefix}user u on u.id = h.idUser
  where h.refType='UserStory' and h.colName='idStatus' and us.idProject=".Sql::fmtId($projectId)." $doneWhereSprintUS and DATE(h.operationDate)=".Sql::str($yesterday);
$doneAC = "select 'Activity' as refType, a.id as refId, a.name, s.name as statusName, h.operationDate, u.fullName as who
  from ${prefix}history h join ${prefix}status s on s.id = CAST(h.newValue as UNSIGNED) and s.setIdleStatus=1
  join ${prefix}activity a on a.id = h.refId and a.idProject=".Sql::fmtId($projectId)."
  left join ${prefix}planningelement pe on pe.refType='Activity' and pe.refId=a.id left join ${prefix}user u on u.id = h.idUser
  where h.refType='Activity' and h.colName='idStatus' and DATE(h.operationDate)=".Sql::str($yesterday)." $doneWhereSprintAC";
$doneRows = array_merge(sqlAll($doneUS), sqlAll($doneAC));
$planWhereSprint = ($spStart && $spEnd) ? " and (pe.plannedStartDate<=".Sql::str($spEnd)." and pe.plannedEndDate>=".Sql::str($spStart).") " : "";
$plan = "select a.id, a.name, r.fullName as resourceName, pe.plannedStartDate, pe.plannedEndDate, s.name as statusName, s.setIdleStatus
  from ${prefix}planningelement pe join ${prefix}activity a on a.id=pe.refId and pe.refType='Activity' and pe.idProject=".Sql::fmtId($projectId)."
  left join ${prefix}assignment ass on ass.refType='Activity' and ass.refId=a.id and ass.idProject=".Sql::fmtId($projectId)."
  left join ${prefix}resource r on r.id=ass.idResource left join ${prefix}status s on s.id=a.idStatus
  where pe.plannedStartDate<=".Sql::str($theDate)." and pe.plannedEndDate>=".Sql::str($theDate)." $planWhereSprint";
$planRows = sqlAll($plan);
$blkWhereSprint = $sprintId ? " and us.idSprint=".Sql::fmtId($sprintId)." " : "";
$blockers = "select distinct i.id, i.name, st.name as statusName
  from ${prefix}issue i left join ${prefix}status st on st.id=i.idStatus
  join ${prefix}link l on ( (l.ref1Type='Issue' and l.ref1Id=i.id) or (l.ref2Type='Issue' and l.ref2Id=i.id) )
  left join ${prefix}userstory us on ( (l.ref1Type='UserStory' and l.ref1Id=us.id) or (l.ref2Type='UserStory' and l.ref2Id=us.id) )
  left join ${prefix}activity a on ( (l.ref1Type='Activity' and l.ref1Id=a.id) or (l.ref2Type='Activity' and l.ref2Id=a.id) )
  where ( (us.idProject=".Sql::fmtId($projectId)." $blkWhereSprint) or (a.idProject=".Sql::fmtId($projectId).") ) and (st.setIdleStatus is null or st.setIdleStatus=0)";
$blkRows = sqlAll($blockers);
?><!DOCTYPE html><html><head><meta charset="utf-8"><title>Daily Scrum</title>
<style>body{font-family:Arial,sans-serif;margin:12px}form{display:flex;gap:8px;align-items:center;margin-bottom:10px}table{width:100%;border-collapse:collapse;margin:6px 0 18px}th,td{border:1px solid #ddd;padding:6px 8px}th{background:#f2f2f2;text-align:left}.muted{color:#666;font-size:12px}.pill{font-size:11px;padding:2px 6px;border-radius:999px;background:#eee}</style></head><body>
<h1>Daily Scrum</h1>
<form method="get"><label>Projet</label><select name="projectId" required><option value="">— choisir —</option><?php foreach (SqlList::getList('Project') as $pid=>$pname){$sel=($pid==$projectId)?' selected':''; echo "<option value=\"$pid\"$sel>".html($pname)."</option>"; } ?></select>
<label>Date</label><input type="date" name="date" value="<?php echo html($theDate); ?>"/>
<label>Sprint</label><select name="sprintId"><option value="">Tous</option><?php if($projectId){ foreach (SqlList::getListWithCrit('Sprint', array('idProject'=>$projectId,'idle'=>'0')) as $sid=>$sname){ $sel=($sid==$sprintId)?' selected':''; echo "<option value=\"$sid\"$sel>".html($sname)."</option>"; }} ?></select>
<button type="submit">Afficher</button><button type="button" onclick="window.print()">Imprimer</button></form>
<?php if (! $projectId) { echo "<p>Sélectionnez un projet, puis cliquez sur Afficher.</p></body></html>"; exit; } ?>
<?php echo "<h2 style='margin:12px 0 6px;'>Depuis hier (".html($yesterday).") — Fini</h2>"; ?>
<?php if (!count($doneRows)) { echo "<p class='muted'>Rien d'achevé hier.</p>"; } else { ?>
<table><tr><th>Type</th><th>ID</th><th>Nom</th><th>Statut</th><th>Par</th><th>Quand</th></tr>
<?php foreach($doneRows as $r){ echo "<tr><td>".html($r['reftype'])."</td><td>".intval($r['refid'])."</td><td>".html($r['name'])."</td><td>".html($r['statusname'])."</td><td>".html($r['who'])."</td><td>".html($r['operationdate'])."</td></tr>"; } ?></table><?php } ?>
<?php echo "<h2 style='margin:12px 0 6px;'>Aujourd'hui (".html($theDate).") — Plan</h2>"; ?>
<?php if (!count($planRows)) { echo "<p class='muted'>Aucune activité planifiée aujourd'hui.</p>"; } else { ?>
<table><tr><th>Ressource</th><th>Activité</th><th>Fenêtre</th><th>Statut</th></tr>
<?php foreach($planRows as $r){ $win=html($r['plannedstartdate'])." → ".html($r['plannedenddate']); echo "<tr><td>".html($r['resourcename'])."</td><td>[".intval($r['id'])."] ".html($r['name'])."</td><td>".$win."</td><td>".html($r['statusname'])."</td></tr>"; } ?></table><?php } ?>
<?php echo "<h2 style='margin:12px 0 6px;'>Blockers — Issues ouvertes liées</h2>"; ?>
<?php if (!count($blkRows)) { echo "<p class='muted'>Aucun bloqueur détecté via les liaisons.</p>"; } else { ?>
<table><tr><th>ID</th><th>Issue</th><th>Statut</th></tr>
<?php foreach($blkRows as $r){ echo "<tr><td>".intval($r['id'])."</td><td>".html($r['name'])."</td><td>".html($r['statusname'])."</td></tr>"; } ?></table><?php } ?>
<p class="muted">NB : rapport minimal basé sur les statuts (clos = setIdleStatus=1), les fenêtres de planification (planningelement), et les liens vers les issues.</p>
</body></html>