-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 10.3.0                                       //
-- // Date : 2022-12-21                                    //
-- ///////////////////////////////////////////////////////////

-- Report RIDA

DELETE FROM `${prefix}reportparameter` WHERE idReport=135;
DELETE FROM `${prefix}report` WHERE id=135;

INSERT INTO `${prefix}report` (`id`, `name`, `idReportCategory`, `file`, `sortOrder`, `idle`, `hasPrint`, `hasPdf`, `hasToday`, `hasWord`, `hasExcel`) 
VALUES (135,'reportRida',10,'rida.php', 1060, 0, 1, 1, 1, 0, 1);

INSERT INTO `${prefix}reportparameter` (`idReport`, `name`, `paramType`, `sortOrder`, `defaultValue`) VALUES
(135, 'idProject', 'projectList', 10, 'currentProject'); 

INSERT INTO `${prefix}habilitationreport` (`idProfile`, `idReport`, `allowAccess`) VALUES 
(1, 135, 1),
(3, 135, 1);

INSERT INTO `${prefix}cronexecution` (`cron`, `fileExecuted`, `idle` ,`fonctionName`) VALUES
('0 1 * * *', '../tool/cronExecutionStandard.php', 1, 'cronRunConsistencyFix');

INSERT INTO `${prefix}reportparameter` (`idReport`, `name`, `paramType`, `sortOrder`, `defaultValue`, `multiple`, `required`) VALUES 
(7, 'showIdle', 'boolean', 45, 0,0,0);

INSERT INTO `${prefix}indicator` (`id`, `code`, `type`, `name`, `sortOrder`, `idle`) VALUES
(32, 'PEOAE', 'percent', 'PlannedExpenseOverAssignedExpense', 275, 0),
(33, 'PEOVE', 'percent', 'PlannedExpenseOverValidatedExpense', 280, 0),
(34, 'REOAE', 'percent', 'RealExpenseOverAssignedExpense', 285, 0),
(35, 'REOVE', 'percent', 'RealExpenseOverValidatedExpense', 290, 0);

INSERT INTO `${prefix}indicatorableindicator` (`idIndicator`, `idIndicatorable`, `nameIndicatorable`, `idle`) VALUES
(32, 8, 'Project', 0),
(33, 8, 'Project', 0),
(34, 8, 'Project', 0),
(35, 8, 'Project', 0);

ALTER TABLE `${prefix}consolidationvalidation` 
ADD `monthlyRevenue` decimal(11,2) DEFAULT NULL;

INSERT INTO `${prefix}menu` (`id`,`name`, `idMenu`, `type`, `sortOrder`, `level`, `idle`, `menuClass`, `isAdminMenu`, `isLeavesSystemMenu`) VALUES 
(286, 'menuAssignment',14,'object',575,'Project',0,'EnvironmentalParameter ',0,0);

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`) VALUES 
(1,286,1),
(3,286,1);  

INSERT INTO `${prefix}accessright` (`idProfile`, `idMenu`, `idAccessProfile`) VALUES 
(1,286, 8),
(3,286, 7);

UPDATE `${prefix}navigation` SET id=100012001 WHERE name='menuImportProject';
UPDATE `${prefix}navigation` SET id=378 WHERE name='menuCriticalResources' and id>378; 
UPDATE `${prefix}navigation` SET id=379 WHERE name='menuResourceMaterial' and id>379; 
INSERT INTO `${prefix}navigation` (`id`,`name`, `idParent`, `idMenu`,`sortOrder`,`idReport`) VALUES
(380,'menuAssignment',128,286,95,0);

INSERT INTO `${prefix}importable` (`id`, `name`, `idle`) VALUES
(71, 'ImputationWork',0),
(72,'ActivityWorkUnit',0);

INSERT INTO `${prefix}report` (`id`, `name`, `idReportCategory`, `file`, `sortOrder`, `hasExcel`, `referTo`) VALUES
(136, 'reportYearlyPlanResourceActivity',2, 'yearlyPlanResourceActivity.php', 290,'1','planYearly');

INSERT INTO `${prefix}reportparameter` (`idReport`, `name`, `paramType`, `sortOrder`, `defaultValue`) VALUES 
(136, 'idProject', 'projectList', 10, 'currentProject'),
(136, 'idOrganization', 'organizationList', 20,null),
(136,'idTeam','teamList',30,null),
(136, 'year', 'year', 40,'currentYear');

INSERT INTO `${prefix}habilitationreport` (`idProfile`, `idReport`, `allowAccess`) VALUES 
(1, 136, 1);

INSERT INTO `${prefix}planningmode` (`id`, `applyTo`, `name`, `code`, `sortOrder`, `idle`, `mandatoryStartDate`, `mandatoryEndDate`) VALUES
(25, 'Activity', 'PlanningModeSTARTREQUIRED', 'STARR', 420, 0 , 1, 0),
(26, 'TestSession', 'PlanningModeSTARTREQUIRED', 'STARR', 420, 0 , 1, 0);

INSERT INTO `${prefix}report` (`id`, `name`, `idReportCategory`, `file`, `sortOrder`, `referTo`) VALUES
(137, 'reportWorkMonthlyByResource',1, 'activityPlan.php?onlyRealWork=true', 200, 'work');

INSERT INTO `${prefix}reportparameter` (`idReport`, `name`, `paramType`, `sortOrder`, `defaultValue`) VALUES 
(137, 'month', 'month', 20, 'currentMonth'),
(137, 'idResource', 'resourceList',10 ,'currentResource'),
(137, 'includeNextMonth', 'boolean', 50, null);

INSERT INTO `${prefix}habilitationreport` (`idProfile`, `idReport`, `allowAccess`) VALUES 
(1, 137, 1);


INSERT INTO `${prefix}report` (`id`, `name`, `idReportCategory`, `file`, `sortOrder`, `referTo`) VALUES
(138, 'reportWorkMonthlyDetailByResource',1, 'detailPlan.php?onlyRealWork=true', 202, 'work');

INSERT INTO `${prefix}reportparameter` (`idReport`, `name`, `paramType`, `sortOrder`, `defaultValue`) VALUES 
(138, 'idProject', 'projectList', 10, 'currentProject'),
(138, 'month', 'month', 20, 'currentMonth'),
(138, 'idTeam', 'teamList', 15,null),
(138, 'idResource', 'resourceList', 17, null),
(138, 'includeNextMonth', 'boolean', 50, null),
(138, 'idOrganization', 'organizationList', 11, null);

INSERT INTO `${prefix}habilitationreport` (`idProfile`, `idReport`, `allowAccess`) VALUES 
(1, 138, 1);

INSERT INTO `${prefix}report` (`id`, `name`, `idReportCategory`, `file`, `sortOrder`, `hasExcel`, `referTo`) VALUES
(139, 'reportWorkYearlyPerMonth',1, 'yearlyResourcePlan.php?onlyRealWork=true', 204, 1, 'work'),
(140, 'reportActionTable',4, 'riskManagementPlan.php?onlyAction=true', 431, 1, null);

INSERT INTO `${prefix}reportparameter` (`idReport`, `name`, `paramType`, `sortOrder`, `defaultValue`) VALUES
(139, 'idProject', 'projectList', 10, 'currentProject'),
(139, 'idOrganization', 'organizationList', 20,null),
(139,'idTeam','teamList',30,null),
(139, 'year', 'year', 40,'currentYear'),
(140, 'idProject', 'projectList', 10, 'currentProject'),
(140, 'showIdle', 'boolean', 20, 0);

INSERT INTO `${prefix}habilitationreport` (`idProfile`, `idReport`, `allowAccess`) VALUES 
(1, 139, 1),
(1, 140, 1);

INSERT INTO `${prefix}habilitationother` (idProfile,scope,rightAccess) VALUES 
(1,'reportAdminProject','1'),
(2,'reportAdminProject','1'),
(3,'reportAdminProject','1'),
(4,'reportAdminProject','2'),
(6,'reportAdminProject','2'),
(7,'reportAdminProject','2'),
(5,'reportAdminProject','2');

UPDATE `${prefix}report` set `hasExcel`=1  WHERE name='reportRiskManagementPlan';

-- PBER : fix storing VotingItems for TicketSimple
DELETE FROM `${prefix}votingitem` where refType='TicketSimple';
DELETE FROM `${prefix}voting` where refType='TicketSimple';

ALTER TABLE `${prefix}votingattribution` 
ADD `endAttributionDate` date DEFAULT NULL;

UPDATE `${prefix}menu` set sortOrder=665 where id=285; 
