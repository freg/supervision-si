-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 12.0.0                                      //
-- // Date : 2024-08-05                                     //
-- ///////////////////////////////////////////////////////////

-- MULTI-CURRENCY

ALTER TABLE `${prefix}activityprice` ADD COLUMN `commissionCostLocal` decimal(10,2) DEFAULT NULL;
ALTER TABLE `${prefix}activityprice` ADD COLUMN `priceCostLocal` decimal(10,2) DEFAULT NULL;
ALTER TABLE `${prefix}activityprice` ADD COLUMN `subcontractorCostLocal` decimal(10,2) DEFAULT NULL;
ALTER TABLE `${prefix}assignment` ADD COLUMN `assignedCostLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}assignment` ADD COLUMN `dailyCostLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}assignment` ADD COLUMN `leftCostLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}assignment` ADD COLUMN `newDailyCostLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}assignment` ADD COLUMN `plannedCostLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}assignment` ADD COLUMN `realCostLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}bill` ADD COLUMN `fullAmountLocal` decimal(12,2) DEFAULT NULL;
ALTER TABLE `${prefix}bill` ADD COLUMN `paymentAmountLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}bill` ADD COLUMN `untaxedAmountLocal` decimal(12,2) DEFAULT NULL;
ALTER TABLE `${prefix}bill` ADD COLUMN `taxAmountLocal` decimal(12,2) DEFAULT NULL;
ALTER TABLE `${prefix}billline` ADD COLUMN `priceLocal` decimal(12,2) DEFAULT NULL;
ALTER TABLE `${prefix}billline` ADD COLUMN `amountLocal` decimal(12,2) DEFAULT NULL;
ALTER TABLE `${prefix}callfortender` ADD COLUMN `maxAmountLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}changerequest` ADD COLUMN `plannedCostLocal` decimal(12,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}command` ADD COLUMN `addFullAmountLocal` decimal(12,2) DEFAULT NULL;
ALTER TABLE `${prefix}command` ADD COLUMN `addPricePerDayAmountLocal` decimal(12,2) DEFAULT NULL;
ALTER TABLE `${prefix}command` ADD COLUMN `addUntaxedAmountLocal` decimal(12,2) DEFAULT NULL;
ALTER TABLE `${prefix}command` ADD COLUMN `fullAmountLocal` decimal(12,2) DEFAULT NULL;
ALTER TABLE `${prefix}command` ADD COLUMN `initialPricePerDayAmountLocal` decimal(12,2) DEFAULT NULL;
ALTER TABLE `${prefix}command` ADD COLUMN `totalFullAmountLocal` decimal(12,2) DEFAULT NULL;
ALTER TABLE `${prefix}command` ADD COLUMN `totalUntaxedAmountLocal` decimal(12,2) DEFAULT NULL;
ALTER TABLE `${prefix}command` ADD COLUMN `untaxedAmountLocal` decimal(12,2) DEFAULT NULL;
ALTER TABLE `${prefix}command` ADD COLUMN `validatedPricePerDayAmountLocal` decimal(12,2) DEFAULT NULL;
ALTER TABLE `${prefix}command` ADD COLUMN `taxAmountLocal` decimal(12,2) DEFAULT NULL;
ALTER TABLE `${prefix}command` ADD COLUMN `addTaxAmountLocal` decimal(12,2) DEFAULT NULL;
ALTER TABLE `${prefix}command` ADD COLUMN `totalTaxAmountLocal` decimal(12,2) DEFAULT NULL;
ALTER TABLE `${prefix}complexityvalues` ADD COLUMN `priceLocal` decimal(12,2) DEFAULT NULL;
ALTER TABLE `${prefix}deliverable` ADD COLUMN `impactCostLocal` decimal(9,0) DEFAULT NULL;
ALTER TABLE `${prefix}delivery` ADD COLUMN `impactCostLocal` decimal(9,0) DEFAULT NULL;
ALTER TABLE `${prefix}expense` ADD COLUMN `plannedAmountLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}expense` ADD COLUMN `plannedFullAmountLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}expense` ADD COLUMN `plannedTaxAmountLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}expense` ADD COLUMN `realAmountLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}expense` ADD COLUMN `realFullAmountLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}expense` ADD COLUMN `realTaxAmountLocal` decimal(14,5) DEFAULT NULL;
ALTER TABLE `${prefix}expensedetail` ADD COLUMN `amountLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}opportunity` ADD COLUMN `impactCostLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}opportunity` ADD COLUMN `projectReserveAmountLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}payment` ADD COLUMN `billAmountLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}payment` ADD COLUMN `paymentAmountLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}payment` ADD COLUMN `paymentCreditAmountLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}payment` ADD COLUMN `paymentFeeAmountLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}plannedwork` ADD COLUMN `costLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}plannedwork` ADD COLUMN `dailyCostLocal` decimal(7,2) DEFAULT NULL;
ALTER TABLE `${prefix}plannedworkbaseline` ADD COLUMN `costLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}plannedworkbaseline` ADD COLUMN `dailyCostLocal` decimal(7,2) DEFAULT NULL;
ALTER TABLE `${prefix}plannedworkmanual` ADD COLUMN `costLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}plannedworkmanual` ADD COLUMN `dailyCostLocal` decimal(7,2) DEFAULT NULL;
ALTER TABLE `${prefix}planningelement` ADD COLUMN `assignedCostLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}planningelement` ADD COLUMN `expenseAssignedAmountLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}planningelement` ADD COLUMN `expenseLeftAmountLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}planningelement` ADD COLUMN `expensePlannedAmountLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}planningelement` ADD COLUMN `expenseRealAmountLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}planningelement` ADD COLUMN `expenseValidatedAmountLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}planningelement` ADD COLUMN `initialCostLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}planningelement` ADD COLUMN `leftCostLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}planningelement` ADD COLUMN `marginCostLocal` decimal(14,5) DEFAULT NULL;
ALTER TABLE `${prefix}planningelement` ADD COLUMN `plannedCostLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}planningelement` ADD COLUMN `realCostLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}planningelement` ADD COLUMN `reserveAmountLocal` decimal(12,2) DEFAULT NULL;
ALTER TABLE `${prefix}planningelement` ADD COLUMN `totalAssignedCostLocal` decimal(12,2) DEFAULT NULL;
ALTER TABLE `${prefix}planningelement` ADD COLUMN `totalLeftCostLocal` decimal(12,2) DEFAULT NULL;
ALTER TABLE `${prefix}planningelement` ADD COLUMN `totalPlannedCostLocal` decimal(12,2) DEFAULT NULL;
ALTER TABLE `${prefix}planningelement` ADD COLUMN `totalRealCostLocal` decimal(12,2) DEFAULT NULL;
ALTER TABLE `${prefix}planningelement` ADD COLUMN `totalValidatedCostLocal` decimal(12,2) DEFAULT NULL;
ALTER TABLE `${prefix}planningelement` ADD COLUMN `validatedCostLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}planningelement` ADD COLUMN `revenueLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}planningelement` ADD COLUMN `commandSumLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}planningelement` ADD COLUMN `billSumLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}planningelementbaseline` ADD COLUMN `assignedCostLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}planningelementbaseline` ADD COLUMN `expenseAssignedAmountLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}planningelementbaseline` ADD COLUMN `expenseLeftAmountLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}planningelementbaseline` ADD COLUMN `expensePlannedAmountLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}planningelementbaseline` ADD COLUMN `expenseRealAmountLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}planningelementbaseline` ADD COLUMN `expenseValidatedAmountLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}planningelementbaseline` ADD COLUMN `initialCostLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}planningelementbaseline` ADD COLUMN `leftCostLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}planningelementbaseline` ADD COLUMN `marginCostLocal` decimal(14,5) DEFAULT NULL;
ALTER TABLE `${prefix}planningelementbaseline` ADD COLUMN `plannedCostLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}planningelementbaseline` ADD COLUMN `realCostLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}planningelementbaseline` ADD COLUMN `reserveAmountLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}planningelementbaseline` ADD COLUMN `totalAssignedCostLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}planningelementbaseline` ADD COLUMN `totalLeftCostLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}planningelementbaseline` ADD COLUMN `totalPlannedCostLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}planningelementbaseline` ADD COLUMN `totalRealCostLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}planningelementbaseline` ADD COLUMN `totalValidatedCostLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}planningelementbaseline` ADD COLUMN `validatedCostLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}planningelementbaseline` ADD COLUMN `revenueLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}projecthistory` ADD COLUMN `leftCostLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}projecthistory` ADD COLUMN `realCostLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}projecthistory` ADD COLUMN `totalLeftCostLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}projecthistory` ADD COLUMN `totalRealCostLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}projecthistory` ADD COLUMN `validatedCostLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}providerbill` ADD COLUMN `discountAmountLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}providerbill` ADD COLUMN `discountFullAmountLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}providerbill` ADD COLUMN `fullAmountLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}providerbill` ADD COLUMN `paymentAmountLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}providerbill` ADD COLUMN `taxAmountLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}providerbill` ADD COLUMN `totalFullAmountLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}providerbill` ADD COLUMN `totalTaxAmountLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}providerbill` ADD COLUMN `totalUntaxedAmountLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}providerbill` ADD COLUMN `untaxedAmountLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}providerorder` ADD COLUMN `discountAmountLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}providerorder` ADD COLUMN `discountFullAmountLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}providerorder` ADD COLUMN `fullAmountLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}providerorder` ADD COLUMN `taxAmountLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}providerorder` ADD COLUMN `totalFullAmountLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}providerorder` ADD COLUMN `totalTaxAmountLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}providerorder` ADD COLUMN `totalUntaxedAmountLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}providerorder` ADD COLUMN `untaxedAmountLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}providerpayment` ADD COLUMN `paymentAmountLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}providerpayment` ADD COLUMN `paymentCreditAmountLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}providerpayment` ADD COLUMN `paymentFeeAmountLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}providerpayment` ADD COLUMN `providerBillAmountLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}providerterm` ADD COLUMN `fullAmountLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}providerterm` ADD COLUMN `taxAmountLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}providerterm` ADD COLUMN `untaxedAmountLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}quotation` ADD COLUMN `fullAmountLocal` decimal(12,2) DEFAULT NULL;
ALTER TABLE `${prefix}quotation` ADD COLUMN `initialAmountLocal` decimal(12,2) DEFAULT NULL;
ALTER TABLE `${prefix}quotation` ADD COLUMN `initialPricePerDayAmountLocal` decimal(12,2) DEFAULT NULL;
ALTER TABLE `${prefix}quotation` ADD COLUMN `untaxedAmountLocal` decimal(12,2) DEFAULT NULL;
ALTER TABLE `${prefix}risk` ADD COLUMN `impactCostLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}risk` ADD COLUMN `projectReserveAmountLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}tender` ADD COLUMN `discountAmountLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}tender` ADD COLUMN `discountFullAmountLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}tender` ADD COLUMN `fullAmountLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}tender` ADD COLUMN `taxAmountLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}tender` ADD COLUMN `totalFullAmountLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}tender` ADD COLUMN `totalTaxAmountLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}tender` ADD COLUMN `totalUntaxedAmountLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}tender` ADD COLUMN `untaxedAmountLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}term` ADD COLUMN `amountLocal` decimal(10,2) DEFAULT NULL;
ALTER TABLE `${prefix}term` ADD COLUMN `plannedAmountLocal` decimal(10,2) DEFAULT NULL;
ALTER TABLE `${prefix}term` ADD COLUMN `validatedAmountLocal` decimal(10,2) DEFAULT NULL;
ALTER TABLE `${prefix}work` ADD COLUMN `costLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}work` ADD COLUMN `dailyCostLocal` decimal(11,2) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}workcommand` ADD COLUMN `unitAmountLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}workcommand` ADD COLUMN `commandAmountLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}workcommand` ADD COLUMN `doneAmountLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}workcommand` ADD COLUMN `billedAmountLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}workcommand` ADD COLUMN `acceptedAmountLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}workelement` ADD COLUMN `leftCostLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}workelement` ADD COLUMN `realCostLocal` decimal(11,2) DEFAULT NULL;
ALTER TABLE `${prefix}worktoken` ADD COLUMN `amountLocal` decimal(13,5) unsigned DEFAULT NULL;
ALTER TABLE `${prefix}worktokenclientcontract` ADD COLUMN `amountLocal` decimal(13,5) unsigned DEFAULT NULL;

ALTER TABLE `${prefix}project` ADD COLUMN `localCurrency` varchar(10) DEFAULT NULL;
ALTER TABLE `${prefix}project` ADD COLUMN `localCurrencyPosition` varchar(10) DEFAULT NULL;
ALTER TABLE `${prefix}project` ADD COLUMN `localToGlobalConversion` decimal(14,5) DEFAULT 0;
ALTER TABLE `${prefix}project` ADD COLUMN `globalToLocalConversion` decimal(14,5) DEFAULT 0;
ALTER TABLE `${prefix}project` ADD COLUMN `inheritedCurrency` int(1) DEFAULT 0;

-- New Screen : Work Command

INSERT INTO `${prefix}menu` (`id`, `name`, `idMenu`, `type`, `sortOrder`, `level`, `idle`, `menuClass`, `isAdminMenu`) VALUES 
(310,'menuWorkCommand', '152', 'object', '245', 'Project', 0, 'Financial',0);

INSERT INTO `${prefix}navigation` (`id`, `name`, `idParent`, `idMenu`,`sortOrder`,`idReport`) VALUES
(402,'menuWorkCommand',14,310,25,0);

-- New Screen Acceptance

ALTER TABLE `${prefix}acceptance` ADD `reference` VARCHAR(100) NULL DEFAULT NULL;
ALTER TABLE `${prefix}acceptance` ADD `idProject` INT UNSIGNED NULL DEFAULT NULL COMMENT '12';

UPDATE `${prefix}menu` SET `idle` = '0' WHERE `${prefix}menu`.`id` = 312;
UPDATE `${prefix}menu` SET `idle` = '0' WHERE `${prefix}menu`.`id` = 311;

INSERT INTO `${prefix}navigation` (`id`, `name`, `idParent`, `idMenu`,`sortOrder`,`idReport`) VALUES
(405,'menuAcceptance',5,311,65,0),
(406,'menuAcceptanceType',330,312,296,0);

UPDATE `${prefix}type` SET `idle` = '0' WHERE `${prefix}type`.`id` = 212;
UPDATE `${prefix}type` SET `idle` = '0' WHERE `${prefix}type`.`id` = 211;
UPDATE `${prefix}type` SET `idWorkflow` = '1' WHERE `${prefix}type`.`id` = 212;
UPDATE `${prefix}type` SET `idWorkflow` = '1' WHERE `${prefix}type`.`id` = 211;

UPDATE `${prefix}copyable` SET `idDefaultCopyable` = '34' WHERE `${prefix}copyable`.`id` = 20;

UPDATE `${prefix}accessright` SET `idAccessProfile` = '1000001' WHERE `${prefix}accessright`.`idMenu` = 312;
UPDATE `${prefix}menu` SET `level` = 'Project' WHERE `${prefix}menu`.`id` = 311;

ALTER TABLE `${prefix}workcommand` ADD `acceptedQuantity` DECIMAL(8,3) NULL DEFAULT NULL;
ALTER TABLE `${prefix}workcommand` ADD `acceptedAmount` DECIMAL(14,2) NULL DEFAULT NULL;
  
ALTER TABLE `${prefix}workcommandaccepted` ADD `idAcceptance` INT UNSIGNED NULL DEFAULT NULL COMMENT '12';
ALTER TABLE `${prefix}workcommandaccepted` ADD `acceptedDate` DATE NULL DEFAULT NULL;
 
INSERT INTO `${prefix}copyable` (`name`, `idle`, `sortOrder`, `idDefaultCopyable`) VALUES ('Acceptance', '0', '930', '15');
 
 INSERT INTO `${prefix}accessright` (`idProfile`, `idMenu`, `idAccessProfile`) VALUES 
(1, 310, 8),
(2, 310, 2),
(3, 310, 7);

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`) VALUES 
(1, 310, 1),
(2, 310, 1),
(3, 310, 1);

INSERT INTO `${prefix}report` (`id`, `name`, `idReportCategory`, `file`, `sortOrder`) VALUES
(145, 'reportAcceptationWorkCommand',7, 'reportAcceptationWorkCommand.php', 906);

INSERT INTO `${prefix}reportparameter` (`idReport`, `name`, `paramType`, `sortOrder`, `defaultValue`, `required`) VALUES 
(145, 'idProject', 'projectList', 10, 'currentProject', 1),
(145,'year','year',20,'currentYear', 1),
(145,'showClosedItems','boolean',40,null,0);

INSERT INTO `${prefix}habilitationreport` (`idProfile`, `idReport`, `allowAccess`) VALUES 
(1, 145, 1),
(2, 145, 1),
(3, 145, 1),
(4, 145, 1),
(6, 145, 1),
(7, 145, 1);

INSERT INTO `${prefix}modulereport` (`idModule`,`idReport`,`hidden`,`active`) VALUES
(7,145,0,1);

ALTER TABLE `${prefix}workcommand` ADD `idWorkCommand` int(12) unsigned DEFAULT NULL COMMENT '12';
ALTER TABLE `${prefix}workcommand` ADD `elementary` int(1) unsigned DEFAULT '1' COMMENT '1';

UPDATE `${prefix}workcommand` set `idProject`=(select idProject from `${prefix}workunit` wu where wu.id=`${prefix}workcommand`.idWorkUnit  ) where idProject is null;

INSERT INTO `${prefix}menu` (`id`, `name`, `idMenu`, `type`, `sortOrder`, `level`, `idle`, `menuClass`, `isAdminMenu`) VALUES 
(313,'menuWorkPlan',7,'item',155,NULL, 0, 'Work', 0);

INSERT INTO `${prefix}navigation` (`id`, `name`, `idParent`, `idMenu`,`sortOrder`,`idReport`) VALUES
(407,'menuWorkPlan',10,313,110,0),
(408,'menuWorkPlan',1,313,71,0);

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`) VALUES
(1, 313, 1),
(2, 313, 1),
(3, 313, 1),
(4, 313, 1),
(5, 313, 1),
(6, 313, 1),
(7, 313, 1);

INSERT INTO `${prefix}habilitationother` (idProfile,scope,rightAccess) VALUES 
(1,'workPlan','1'),
(2,'workPlan','1'),
(3,'workPlan','1'),
(4,'workPlan','2'),
(6,'workPlan','2'),
(7,'workPlan','2'),
(5,'workPlan','2');

ALTER TABLE `${prefix}link` ADD COLUMN `idSynchronizationItem` int(12) unsigned DEFAULT NULL COMMENT '12';

CREATE TABLE `${prefix}workdetail` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
`idWork` int(12) unsigned DEFAULT NULL COMMENT '12',
`work` DECIMAL (8,5),
`idWorkCategory` int(12) unsigned DEFAULT NULL COMMENT '12',
`uncertainties` varchar(4000) DEFAULT NULL,
`progress` varchar(4000) DEFAULT NULL,
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

CREATE TABLE `${prefix}workcategory` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
`refType` varchar(100) DEFAULT NULL,
`refId` int(12) unsigned DEFAULT NULL COMMENT '12',
`name` varchar(100) DEFAULT NULL,
`sortOrder` int(3) unsigned DEFAULT '0' COMMENT '3',
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;


CREATE TABLE `${prefix}planninghistory` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `date`  datetime DEFAULT NULL,
  `idUser` int(12) unsigned DEFAULT NULL COMMENT '12',
  `projects`  mediumtext DEFAULT NULL,
  `startDate` datetime DEFAULT NULL,
  `startTime` varchar(100) DEFAULT NULL,
  `endTime` varchar(100) DEFAULT NULL,
  `result` varchar(100) DEFAULT NULL,
  `resultDescription` mediumtext DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

ALTER TABLE `${prefix}tag` ADD `idProject` int(12) unsigned DEFAULT NULL COMMENT '12';

INSERT INTO `${prefix}report` (`id`, `name`, `idReportCategory`, `file`, `sortOrder`) VALUES
(146, 'reportListOfWorksForAnActivity',1, 'reportListOfWorksForAnActivity.php', 480);

INSERT INTO `${prefix}reportparameter` (`idReport`, `name`, `paramType`, `sortOrder`, `defaultValue`, `required`) VALUES 
(146, 'idProject', 'projectList', 10, 'currentProject', 1),
(146,'idActivity','activityList',20,null,0);

INSERT INTO `${prefix}habilitationreport` (`idProfile`, `idReport`, `allowAccess`) VALUES 
(1, 146, 1);

INSERT INTO `${prefix}modulereport` (`idModule`,`idReport`,`hidden`,`active`) VALUES
(1,146,0,1);

INSERT INTO `${prefix}habilitationother` (idProfile, scope , rightAccess)
VALUES (1 , 'canWorkOnImputation', '1');

INSERT INTO `${prefix}habilitationother` (idProfile, scope, rightAccess)
SELECT id, 'canWorkOnImputation', '2' FROM `${prefix}profile` WHERE id != 1;

-- PBER #8584
INSERT INTO `${prefix}dependable` (id, name , idle, scope, idDefaultDependable)
VALUES (8 , 'Ticket', 0, 'T', 1),
(9 , 'Action', 0, 'ST', 1),
(10 , 'Decision', 0, 'ST', 1),
(11 , 'Incoming', 0, 'ST', 1),
(12 , 'Deliverable', 0, 'ST', 1),
(13 , 'Delivery', 0, 'ST', 1),
(14 , 'Opportunity', 0, 'ST', 1),
(15 , 'Issue', 0, 'ST', 1),
(16 , 'Question', 0, 'ST', 1),
(17 , 'Risk', 0, 'ST', 1);

-- Restriction of lists per project

CREATE TABLE `${prefix}listhidevalue` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `nameList`  varchar(100) DEFAULT NULL,
  `idProject` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idValue` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idUser` int(12) unsigned DEFAULT NULL COMMENT '12',
  PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

-- Add report of tokens on 
ALTER TABLE `${prefix}worktokenclientcontract` ADD `reportQuantity` decimal(7,2) DEFAULT NULL;
ALTER TABLE `${prefix}worktokenclientcontract` ADD `newQuantity` decimal(7,2) DEFAULT NULL;