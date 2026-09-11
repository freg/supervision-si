-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 9.1.2                                       //
-- // Date : 2021-03-20                                     //
-- ///////////////////////////////////////////////////////////
-- Patch on V9.2

DELETE FROM `${prefix}modulemenu` WHERE `idMenu`=257;

INSERT INTO `${prefix}habilitationother` (idProfile, scope , rightAccess) VALUES
(1,'subtask','1'),
(2,'subtask','1'),
(3,'subtask','1'),
(4,'subtask','1'),
(5,'subtask','2'),
(6,'subtask','2'),
(7,'subtask','2');

UPDATE `${prefix}filtercriteria` set sqlAttribute='idDeliveryType' 
where sqlAttribute='idDeliverableType' and idFilter in (select id from `${prefix}filter` where refType='Delivery');

UPDATE `${prefix}columnselector` set field='nameDeliveryType', attribute='idDeliveryType', name='idDeliveryType'
where attribute='idDeliverableType' and objectClass='Delivery';

-- Fix issue for 
DELETE FROM `${prefix}accessright` where idMenu=222;